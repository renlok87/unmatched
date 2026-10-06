// AU-S5 (docs/game-design/audio/07-production-log.md §9): the mix bus of the main submix - the make-up gain that brings a
// match at the default volumes to -20 LUFS-I and a look-ahead peak limiter that guarantees the sample ceiling. The
// engine's dynamics processor follows a smoothed |x| and let 2 ms transients through ~3.6 dB over its threshold
// (Unmatched.S08.Audio.LimiterProbe), so the ceiling is enforced here per sample.
#pragma once

#include "CoreMinimal.h"
#include "Sound/SoundEffectSubmix.h"

#include "S08MixLimiter.generated.h"

/** World-free DSP core: interleaved frames in, the same frames out. The input is multiplied by the make-up gain and
 *  delayed by the look-ahead; the gain falls ahead of a peak (the minimum required gain over the look-ahead window,
 *  smoothed) and is clamped by the gain the delayed frame itself needs, so no output sample exceeds the ceiling. */
class UNMATCHED_API FS08PeakLimiter {
public:
  void Init(int32 InChannels, float InSampleRate, float CeilingDb, float MakeupDb, float LookaheadMs = 5.0f,
            float ReleaseMs = 120.0f);
  void Process(const float* In, float* Out, int32 Frames);
  int32 Channels() const { return NumChannels; }
  /** The lowest gain applied since Init (1 = never limited) - for the trace and the tests. */
  float MinGain() const { return LowestGain; }

private:
  int32 NumChannels = 0;
  int32 Lookahead = 1;
  float Ceiling = 1.0f;
  float Makeup = 1.0f;
  float AttackCoef = 0.0f;
  float ReleaseCoef = 0.0f;
  float Gain = 1.0f;
  float LowestGain = 1.0f;
  TArray<float> Delay;     // Lookahead frames x channels (already with the make-up gain)
  TArray<float> Required;  // the gain each delayed frame needs
  int32 Pos = 0;
  float WindowMin = 1.0f;
  int32 WindowMinAge = 0;
};

USTRUCT(BlueprintType)
struct UNMATCHED_API FS08MixLimiterSettings {
  GENERATED_BODY()

  UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Limiter)
  float CeilingDb = -1.5f;

  UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Limiter)
  float MakeupDb = 0.0f;

  UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Limiter)
  float LookaheadMs = 5.0f;

  UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Limiter)
  float ReleaseMs = 120.0f;
};

class UNMATCHED_API FS08MixLimiter : public FSoundEffectSubmix {
public:
  virtual void Init(const FSoundEffectSubmixInitData& InInitData) override;
  virtual void OnPresetChanged() override;
  virtual void OnProcessAudio(const FSoundEffectSubmixInputData& InData, FSoundEffectSubmixOutputData& OutData) override;

private:
  FS08PeakLimiter Limiter;
  FS08MixLimiterSettings Current;
  float SampleRate = 48000.0f;
  bool bDirty = true;
};

UCLASS(ClassGroup = AudioSourceEffect)
class UNMATCHED_API US08MixLimiterPreset : public USoundEffectSubmixPreset {
  GENERATED_BODY()

public:
  EFFECT_PRESET_METHODS(S08MixLimiter)

  void SetSettings(const FS08MixLimiterSettings& InSettings) { UpdateSettings(InSettings); }

  UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = SubmixEffectPreset, meta = (ShowOnlyInnerProperties))
  FS08MixLimiterSettings Settings;
};
