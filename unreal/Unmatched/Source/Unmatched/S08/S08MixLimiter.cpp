#include "S08MixLimiter.h"

void FS08PeakLimiter::Init(int32 InChannels, float InSampleRate, float CeilingDb, float MakeupDb, float LookaheadMs,
                           float ReleaseMs) {
  NumChannels = FMath::Max(1, InChannels);
  Lookahead = FMath::Max(1, FMath::RoundToInt(InSampleRate * LookaheadMs / 1000.0f));
  Ceiling = FMath::Pow(10.0f, CeilingDb / 20.0f);
  Makeup = FMath::Pow(10.0f, MakeupDb / 20.0f);
  // the fall spreads over the look-ahead (it reaches ~99 % of the target by the time the peak leaves the delay)
  AttackCoef = FMath::Exp(-5.0f / Lookahead);
  ReleaseCoef = FMath::Exp(-1.0f / FMath::Max(1.0f, InSampleRate * ReleaseMs / 1000.0f));
  Gain = 1.0f;
  LowestGain = 1.0f;
  Delay.Init(0.0f, Lookahead * NumChannels);
  Required.Init(1.0f, Lookahead);
  Pos = 0;
  WindowMin = 1.0f;
  WindowMinAge = 0;
}

void FS08PeakLimiter::Process(const float* In, float* Out, int32 Frames) {
  for (int32 F = 0; F < Frames; ++F) {
    const float* Frame = In + F * NumChannels;
    float Peak = 0.0f;
    for (int32 C = 0; C < NumChannels; ++C) Peak = FMath::Max(Peak, FMath::Abs(Frame[C] * Makeup));
    const float Need = Peak > Ceiling ? Ceiling / Peak : 1.0f;
    // the oldest frame leaves the delay now; its own required gain is the hard clamp
    const float NeedOut = Required[Pos];
    float* Slot = Delay.GetData() + Pos * NumChannels;
    float* Dst = Out + F * NumChannels;
    for (int32 C = 0; C < NumChannels; ++C) {
      Dst[C] = Slot[C];
      Slot[C] = Frame[C] * Makeup;
    }
    Required[Pos] = Need;
    Pos = (Pos + 1) % Lookahead;
    // the minimum required gain over the window (the frames still in the delay, the new one included)
    if (Need <= WindowMin) {
      WindowMin = Need;
      WindowMinAge = 0;
    } else if (++WindowMinAge >= Lookahead) {
      WindowMin = 1.0f;
      for (const float R : Required) WindowMin = FMath::Min(WindowMin, R);
      WindowMinAge = 0;
    }
    Gain = WindowMin < Gain ? WindowMin + (Gain - WindowMin) * AttackCoef : WindowMin + (Gain - WindowMin) * ReleaseCoef;
    const float Applied = FMath::Min(Gain, NeedOut);
    LowestGain = FMath::Min(LowestGain, Applied);
    for (int32 C = 0; C < NumChannels; ++C) Dst[C] *= Applied;
  }
}

void FS08MixLimiter::Init(const FSoundEffectSubmixInitData& InInitData) {
  SampleRate = InInitData.SampleRate;
  OnPresetChanged();  // the preset is attached before Init: start with its settings, not the defaults
}

void FS08MixLimiter::OnPresetChanged() {
  GET_EFFECT_SETTINGS(S08MixLimiter);
  Current = Settings;
  bDirty = true;
}

void FS08MixLimiter::OnProcessAudio(const FSoundEffectSubmixInputData& InData, FSoundEffectSubmixOutputData& OutData) {
  if (bDirty || Limiter.Channels() != InData.NumChannels) {
    Limiter.Init(InData.NumChannels, SampleRate, Current.CeilingDb, Current.MakeupDb, Current.LookaheadMs,
                 Current.ReleaseMs);
    bDirty = false;
  }
  Limiter.Process(InData.AudioBuffer->GetData(), OutData.AudioBuffer->GetData(), InData.NumFrames);
}
