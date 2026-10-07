// VS-4 HB-35 / HB-36 forms: the deferred choice block - see UmHudPending.h.
#include "UmHudPending.h"

#include "../../S09/S09ManeuverUi.h"
#include "../../S09/S09PendingPresent.h"
#include "../S08AnimatedIconWidget.h"
#include "../S08ArtHud.h"
#include "UmButton.h"
#include "UmCardWidget.h"
#include "UmDeckRow.h"
#include "UmGameHud.h"
#include "UmHudStatusLine.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateNoResource.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Components/ScrollBox.h"
#include "Components/ScrollBoxSlot.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Styling/SlateTypes.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "Rendering/SlateRenderer.h"

const TCHAR* const UUmHudPending::WidgetBlueprintPath = TEXT("/Game/S08/UI/Hud/WBP_UI_HUD_PENDING");

bool FUmPendingModel::operator==(const FUmPendingModel& O) const {
  return View == O.View && Body == O.Body && Compact == O.Compact && Kind == O.Kind && HeadId == O.HeadId && Title == O.Title &&
         Text == O.Text && Icon == O.Icon && QueueMore == O.QueueMore && Options == O.Options && Selected == O.Selected &&
         Cards == O.Cards && HeroSlug == O.HeroSlug && PickNeed == O.PickNeed && PickHave == O.PickHave && Number == O.Number &&
         bConfirm == O.bConfirm && ConfirmKey == O.ConfirmKey && ConfirmWhy.Key == O.ConfirmWhy.Key &&
         ConfirmWhy.Args.OrderIndependentCompareEqual(O.ConfirmWhy.Args) && bSecondary == O.bSecondary &&
         SecondaryKey == O.SecondaryKey && bStay == O.bStay && bDecline == O.bDecline && bBack == O.bBack &&
         bCollapse == O.bCollapse && BusyWhy.Key == O.BusyWhy.Key;
}

FBox2D FUmPendingPlan::Find(FName Button) const {
  for (const TPair<FName, FBox2D>& B : Buttons) {
    if (B.Key == Button) return B.Value;
  }
  return FBox2D(ForceInit);
}

namespace {
float UmPdMeasureAt(const FString& Text, float SizeSu, FName Token, float PxPerSu);  // below, with the widget helpers

FBox2D UmPdBox(float X, float Y, float W, float H) { return FBox2D(FVector2D(X, Y), FVector2D(X + W, Y + H)); }

FText UmPdText(const FString& Key, const FFormatNamedArguments* Args = nullptr) {
  const EUmTable Table = Key.StartsWith(TEXT("ms.")) ? EUmTable::Ms : Key.StartsWith(TEXT("why.")) ? EUmTable::Why : EUmTable::Hud;
  return Args ? UmText::Format(Table, Key, *Args) : UmText::Get(Table, Key);
}

FString UmPdString(const FString& Key, const FFormatNamedArguments* Args = nullptr) { return UmPdText(Key, Args).ToString(); }

int32 UmPdRows(const FString& Text, float WrapSu, float SizeSu, FName Token, UmHudPending::FMeasure Measure) {
  if (Text.IsEmpty()) return 0;
  // the rows are counted in a box TextSlackSu narrower than the one the text block wraps in: a row too many makes the
  // plate taller, a row too few would push the last line out of it (the gallery's «… до / 3»)
  return FMath::Max(1, UmHudStatus::WrapLines(Text, FMath::Max(1.0f, WrapSu - UmHudPending::TextSlackSu), SizeSu,
                                               [&Measure, Token](const FString& T, float S) { return Measure(T, S, Token); }));
}

const FName NBack(TEXT("Back"));
const FName NDecline(TEXT("Decline"));
const FName NStay(TEXT("Stay"));
const FName NConfirm(TEXT("Confirm"));
const FName NSecondary(TEXT("Secondary"));
const FName NCollapse(TEXT("Collapse"));
const FName NExpand(TEXT("Expand"));
const FName NCounter(TEXT("Counter"));
const FName NQueue(TEXT("Queue"));

/** The buttons of a form, left to right (the primary second to last, «Свернуть» last - HB-34 footer). */
TArray<FName> UmPdButtons(const FUmPendingModel& M) {
  TArray<FName> Out;
  if (M.View == EUmPendingView::Modal || M.View == EUmPendingView::Compact) {
    if (M.bBack) Out.Add(NBack);
    if (M.bStay) Out.Add(NStay);
    if (M.bDecline) Out.Add(NDecline);
    if (M.bConfirm) Out.Add(NConfirm);
    if (M.bSecondary) Out.Add(NSecondary);
    if (M.bCollapse) Out.Add(NCollapse);
  }
  return Out;
}
}  // namespace

namespace UmHudPending {
float MeasureAtSu(const FString& Text, float SizeSu, FName Token, float PxPerSu) { return UmPdMeasureAt(Text, SizeSu, Token, PxPerSu); }

const TCHAR* ViewName(EUmPendingView View) {
  switch (View) {
    case EUmPendingView::Modal: return TEXT("modal");
    case EUmPendingView::Compact: return TEXT("compact");
    case EUmPendingView::Collapsed: return TEXT("collapsed");
    case EUmPendingView::Toast: return TEXT("toast");
    case EUmPendingView::Opp: return TEXT("opp");
    case EUmPendingView::AfterCombat: return TEXT("compact");  // 04 §2.8: «Выполните после боя» is a grey compact
    default: return TEXT("");
  }
}

const TCHAR* BodyName(EUmPendingBody Body) {
  switch (Body) {
    case EUmPendingBody::Options: return TEXT("options");
    case EUmPendingBody::Pick: return TEXT("pick");
    case EUmPendingBody::Order: return TEXT("order");
    case EUmPendingBody::Number: return TEXT("number");
    default: return TEXT("text");
  }
}

float ToastWidthSu(bool bClassS, bool bTall) { return bClassS ? 440.0f : (bTall ? 560.0f : 520.0f); }

float ButtonWidthSu(const FString& Label, FMeasure Measure) {
  // the label (caps, type.button 20 su) + the button's 2 x 16 su padding + 8 su of slack: the measure answers whole
  // pixels at 1 px per su and the bold caps run a little wider on screen - a label is never cut (HB-34 P11)
  // the caps as UUmButton draws them: FText::ToUpper (ICU - FString::ToUpper leaves Cyrillic lower case, narrower)
  const FString Caps = FText::FromString(Label).ToUpper().ToString();
  return FMath::Max(120.0f, FMath::CeilToFloat(Measure(Caps, 20.0f, FName(TEXT("type.button")))) + 2.0f * 16.0f + TextSlackSu);
}

FString FirstSentence(const FString& Text) {
  const FString T = Text.TrimStartAndEnd();
  for (int32 I = 0; I < T.Len(); ++I) {
    const TCHAR C = T[I];
    if ((C == TEXT('.') || C == TEXT('!') || C == TEXT('?')) && (I + 1 == T.Len() || FChar::IsWhitespace(T[I + 1]))) {
      return T.Left(I + 1);
    }
  }
  return T;
}

FUmPendingPlan Plan(const FUmPendingModel& M, const FUmPendingFrame& F, const TMap<FName, FString>& Labels, FMeasure Measure) {
  FUmPendingPlan P;
  if (M.View == EUmPendingView::Hidden) return P;
  const float CW = static_cast<float>(F.CanvasSu.X);
  const FName Heading(TEXT("type.heading")), BodyTok(TEXT("type.body")), TagTok(TEXT("type.tag"));
  auto Label = [&Labels](FName N) {
    const FString* L = Labels.Find(N);
    return L ? *L : FString();
  };
  auto Width = [&](FName N) { return ButtonWidthSu(Label(N), Measure); };
  const TArray<FName> Names = UmPdButtons(M);
  float BW = 0.0f;
  for (const FName& N : Names) BW += Width(N) + (BW > 0.0f ? ButtonGapSu : 0.0f);
  auto PlaceButtons = [&](float Right, float Y) {
    float X = Right - BW;
    for (const FName& N : Names) {
      const float W = Width(N);
      P.Buttons.Add(TPair<FName, FBox2D>(N, UmPdBox(X, Y, W, ButtonHSu)));
      X += W + ButtonGapSu;
    }
  };
  const float QueueW = M.QueueMore > 0 ? FMath::Max(64.0f, FMath::CeilToFloat(Measure(Label(NQueue), 14.0f, TagTok)) + 24.0f) : 0.0f;

  // ---- modal ----
  if (M.View == EUmPendingView::Modal) {
    const float W = F.ModalWidthSu;
    const float X = 0.5f * (CW - W);
    const float Y = F.TopSu;
    const float TitleRoom = W - 2.0f * ModalPadSu - (QueueW > 0.0f ? QueueW + 8.0f : 0.0f);
    P.TitleRows = M.Title.IsEmpty() ? 0 : UmPdRows(M.Title, TitleRoom, ModalTitleSu, FName(TEXT("type.title")), Measure);
    const float TitleExtra = FMath::Max(0, P.TitleRows - 1) * 34.0f;
    if (P.TitleRows > 0) P.Title = UmPdBox(X + ModalPadSu, Y + 12.0f, TitleRoom, 32.0f + TitleExtra);
    if (QueueW > 0.0f) P.Queue = UmPdBox(X + W - ModalPadSu - QueueW, Y + 16.0f, QueueW, OrderChipSu);
    const float BodyTop = (P.TitleRows > 0 ? BodyTopSu : 16.0f) + TitleExtra;
    const float BodyW = W - 2.0f * ModalPadSu;
    const int32 TextRows = UmPdRows(M.Text, BodyW - 8.0f, 16.0f, BodyTok, Measure);
    P.BodyTextSu = TextRows * BodyLineSu;
    const float Lead = P.BodyTextSu > 0.0f ? P.BodyTextSu + 12.0f : 0.0f;
    const FVector2D Card = F.bClassS ? FVector2D(120.0, 166.0) : FVector2D(150.0, 208.0);
    float Content = P.BodyTextSu;
    switch (M.Body) {
      case EUmPendingBody::Options: {
        const int32 N = M.Options.Num();
        Content = Lead + N * ButtonHSu + FMath::Max(0, N - 1) * ButtonGapSu;
        break;
      }
      case EUmPendingBody::Pick:
      case EUmPendingBody::Order: {
        const bool bPick = M.Body == EUmPendingBody::Pick;
        const float Extra = bPick ? CardRaiseSu : 28.0f;
        Content = Lead + Extra + static_cast<float>(Card.Y);
        const int32 N = M.Cards.Num();
        const float Gap = bPick ? (N > 1 ? FMath::Max(0.0f, (BodyW - N * static_cast<float>(Card.X)) / (N - 1)) : 0.0f) : 16.0f;
        const float RowW = N * static_cast<float>(Card.X) + FMath::Max(0, N - 1) * Gap;
        const float Start = 0.5f * (BodyW - RowW);
        const float CardY = Lead + Extra;
        for (int32 I = 0; I < N; ++I) {
          const float CX = Start + I * (static_cast<float>(Card.X) + Gap);
          const float Raise = bPick && M.Cards[I].bMarked ? CardRaiseSu : 0.0f;
          P.Cards.Add(UmPdBox(CX, CardY - Raise, static_cast<float>(Card.X), static_cast<float>(Card.Y)));
          if (!bPick) P.Chips.Add(UmPdBox(CX + 0.5f * static_cast<float>(Card.X) - 0.5f * OrderChipSu, CardY - 28.0f, OrderChipSu, OrderChipSu));
        }
        break;
      }
      case EUmPendingBody::Number:
        Content = Lead + UmNumberPicker::HeightSu(!M.Number.Result.IsEmpty());
        break;
      default:
        break;
    }
    P.ContentSu = Content;
    // the footer: the counter (PICK) left, the buttons right; a second row when they do not fit (never cut)
    const float CounterW = M.Body == EUmPendingBody::Pick ? FMath::CeilToFloat(Measure(Label(NCounter), 14.0f, TagTok)) + 8.0f : 0.0f;
    const float Room = W - 2.0f * ModalPadSu - (CounterW > 0.0f ? CounterW + 16.0f : 0.0f);
    const int32 FooterRows = BW <= Room ? 1 : 2;
    const float Footer = FooterSu + (FooterRows - 1) * (ButtonHSu + ButtonGapSu);
    const float H = FMath::Min(F.ModalCapSu, BodyTop + Content + FooterGapSu + Footer);
    const float FooterY = Y + H - Footer;
    const float Visible = FMath::Max(0.0f, FooterY - FooterGapSu - (Y + BodyTop));
    P.ScrollSu = FMath::Max(0.0f, Content - Visible);
    P.BodyView = UmPdBox(X + ModalPadSu, Y + BodyTop, BodyW, Visible);
    P.Panel = UmPdBox(X, Y, W, H);
    if (CounterW > 0.0f) P.Counter = UmPdBox(X + ModalPadSu, FooterY, CounterW, ButtonHSu);
    PlaceButtons(X + W - ModalPadSu, FooterY + (FooterRows - 1) * (ButtonHSu + ButtonGapSu));
    return P;
  }

  // ---- collapsed: «{card}: выбор ждёт» + C ----
  if (M.View == EUmPendingView::Collapsed) {
    const FString Key = Label(FName(TEXT("KeyC")));
    const float ChipW = FMath::Max(24.0f, FMath::CeilToFloat(Measure(Key, 14.0f, TagTok)) + 12.0f);
    const float TextW = FMath::CeilToFloat(Measure(M.Text, 16.0f, BodyTok)) + TextSlackSu;
    const float W = FMath::Max(CollapsedWSu, TextW + 8.0f + ChipW + 32.0f);
    const float X = 0.5f * (CW - W);
    const float Y = F.TopSu;
    P.Panel = UmPdBox(X, Y, W, CollapsedHSu);
    P.Hint = UmPdBox(X + 16.0f, Y, W - 32.0f - ChipW - 8.0f, CollapsedHSu);
    P.HintRows = 1;
    P.Keys.Add(TPair<FString, FBox2D>(Key, UmPdBox(X + W - 16.0f - ChipW, Y + 10.0f, ChipW, 24.0f)));
    P.Buttons.Add(TPair<FName, FBox2D>(NExpand, P.Panel));
    return P;
  }

  // ---- toast: the source and «В прошлый раз: {choice}», key chips Enter / X / C ----
  if (M.View == EUmPendingView::Toast) {
    const float W = F.ToastSu.bIsValid ? static_cast<float>(F.ToastSu.GetSize().X) : ToastWidthSu(F.bClassS, true);
    const float Bottom = F.ToastSu.bIsValid ? static_cast<float>(F.ToastSu.Max.Y) : static_cast<float>(F.CanvasSu.Y) - 160.0f;
    const float X = F.ToastSu.bIsValid ? static_cast<float>(F.ToastSu.Min.X) : 0.5f * (CW - W);
    TArray<FString> Keys = {Label(FName(TEXT("KeyEnter"))), Label(FName(TEXT("KeyX"))), Label(FName(TEXT("KeyC")))};
    float KW = 0.0f;
    TArray<float> KWs;
    for (const FString& K : Keys) {
      KWs.Add(FMath::Max(24.0f, FMath::CeilToFloat(Measure(K, 14.0f, TagTok)) + 12.0f));
      KW += KWs.Last() + (KW > 0.0f ? 8.0f : 0.0f);
    }
    const float Room = W - 32.0f - KW - 8.0f;
    const int32 Rows = FMath::Max(1, UmPdRows(M.Text, Room, 16.0f, BodyTok, Measure));
    const float H = FMath::Max(ToastHSu, 4.0f + (M.Title.IsEmpty() ? 0.0f : 20.0f) + Rows * 20.0f + 4.0f);  // HB-34: 48
    const float Y = Bottom - H;
    P.Panel = UmPdBox(X, Y, W, H);
    if (!M.Title.IsEmpty()) {
      P.Title = UmPdBox(X + 16.0f, Y + 4.0f, Room, 20.0f);
      P.TitleRows = 1;
    }
    P.Hint = UmPdBox(X + 16.0f, Y + (M.Title.IsEmpty() ? 14.0f : 24.0f), Room, Rows * 20.0f);
    P.HintRows = Rows;
    float KX = X + W - 16.0f - KW;
    for (int32 I = 0; I < Keys.Num(); ++I) {
      P.Keys.Add(TPair<FString, FBox2D>(Keys[I], UmPdBox(KX, Y + 0.5f * (H - 24.0f), KWs[I], 24.0f)));
      KX += KWs[I] + 8.0f;
    }
    P.Buttons.Add(TPair<FName, FBox2D>(NExpand, P.Panel));
    return P;
  }

  // ---- grey: the opponent's choice, my choice after the combat ----
  if (M.View == EUmPendingView::Opp || M.View == EUmPendingView::AfterCombat) {
    const float Pad = 16.0f;
    const float TW = M.Title.IsEmpty() ? 0.0f : FMath::CeilToFloat(Measure(M.Title, 24.0f, Heading)) + TextSlackSu;
    const float LW = M.Text.IsEmpty() ? 0.0f : FMath::CeilToFloat(Measure(M.Text, 16.0f, BodyTok)) + TextSlackSu;
    const float Cap = CompactLSu;
    const float X0 = F.TopSu;
    (void)X0;
    if (F.bClassS) {
      // one row: [card] [line]
      const float Needed = TW + (TW > 0.0f && LW > 0.0f ? 8.0f : 0.0f) + LW + 2.0f * Pad;
      const float W = FMath::Clamp(Needed, GreyMinSu, Cap);
      float X = 0.5f * (CW - W);
      if (F.BandRightSu > F.BandLeftSu && (X < F.BandLeftSu || X + W > F.BandRightSu)) {
        X = FMath::Max(F.BandLeftSu, 0.5f * (F.BandLeftSu + F.BandRightSu - W));
      }
      const bool bFits = Needed <= Cap;
      const float H = bFits ? 48.0f : 60.0f;
      P.Panel = UmPdBox(X, F.TopSu, W, H);
      if (TW > 0.0f) {
        P.Title = UmPdBox(X + Pad, F.TopSu + (bFits ? 0.5f * (H - 28.0f) : 8.0f), FMath::Min(TW, W - 2.0f * Pad), 28.0f);
        P.TitleRows = 1;
      }
      if (LW > 0.0f) {
        P.Hint = bFits ? UmPdBox(X + Pad + TW + (TW > 0.0f ? 8.0f : 0.0f), F.TopSu + 0.5f * (H - 20.0f), LW, 20.0f)
                       : UmPdBox(X + Pad, F.TopSu + 36.0f, W - 2.0f * Pad, 20.0f);
        P.HintRows = 1;
      }
      return P;
    }
    const float W = FMath::Clamp(FMath::Max(TW, LW) + 2.0f * Pad, GreyMinSu, Cap);
    const float X = 0.5f * (CW - W);
    const int32 TRows = TW > 0.0f ? UmPdRows(M.Title, W - 2.0f * Pad, 24.0f, Heading, Measure) : 0;
    const int32 LRows = LW > 0.0f ? UmPdRows(M.Text, W - 2.0f * Pad, 16.0f, BodyTok, Measure) : 0;
    const float TH = TRows > 0 ? 24.0f + (TRows - 1) * TitleLineSu : 0.0f;
    const float LH = LRows > 0 ? 16.0f + (LRows - 1) * BodyLineSu : 0.0f;
    const float H = FMath::Max(48.0f, TH + (TH > 0.0f && LH > 0.0f ? 4.0f : 0.0f) + LH + 16.0f + (TH > 0.0f && LH > 0.0f ? 0.0f : 0.0f));
    P.Panel = UmPdBox(X, F.TopSu, W, H + (TH > 0.0f && LH > 0.0f ? 0.0f : 0.0f));
    if (TRows > 0) {
      P.Title = UmPdBox(X + Pad, F.TopSu + (LRows > 0 ? 8.0f : 0.5f * (H - TH)), W - 2.0f * Pad, TH);
      P.TitleRows = TRows;
    }
    if (LRows > 0) {
      P.Hint = UmPdBox(X + Pad, F.TopSu + (TRows > 0 ? 8.0f + TH + 4.0f : 0.5f * (H - LH)), W - 2.0f * Pad, LH);
      P.HintRows = LRows;
    }
    return P;
  }

  // ---- compact (own): board, hand pick, discard, boost ----
  const bool bBoost = M.Compact == EUmPendingCompact::Boost;
  const float IconW = M.Icon.IsNone() ? 0.0f : 32.0f;
  if (!F.bClassS && !bBoost) {
    // class L: two rows (card name with its glyph and queue chip; the hint) and the buttons right (HB-34 «text-left»)
    const float W = CompactLSu;
    const float Pad = 12.0f;
    const float X = 0.5f * (CW - W);
    const float Y = F.TopSu;
    const float Left = W - 2.0f * Pad - (BW > 0.0f ? BW + 12.0f : 0.0f);
    const float TitleW = Left - IconW - (QueueW > 0.0f ? QueueW + 8.0f : 0.0f);
    P.TitleRows = M.Title.IsEmpty() ? 0 : UmPdRows(M.Title, TitleW, 24.0f, Heading, Measure);
    P.HintRows = M.Text.IsEmpty() ? 0 : UmPdRows(M.Text, Left, 16.0f, BodyTok, Measure);
    const float TH = P.TitleRows > 0 ? 24.0f + (P.TitleRows - 1) * TitleLineSu : 0.0f;
    const float HH = P.HintRows > 0 ? 16.0f + (P.HintRows - 1) * BodyLineSu : 0.0f;
    const float Inner = TH + (TH > 0.0f && HH > 0.0f ? 4.0f : 0.0f) + HH;
    const float H = FMath::Max(CompactMinHSu, FMath::Max(BW > 0.0f ? ButtonHSu : 0.0f, Inner) + 16.0f);
    // HB-34 «title-full»: the card name across the plate, the hint beside the buttons in the second row - taken when
    // it is lower (a long EN name wraps in «text-left», «The Hounds of Mighty Zeus» beside two buttons)
    if (BW > 0.0f && P.TitleRows > 0) {
      const float TitleWB = W - 2.0f * Pad - IconW - (QueueW > 0.0f ? QueueW + 8.0f : 0.0f);
      const int32 TRowsB = UmPdRows(M.Title, TitleWB, 24.0f, Heading, Measure);
      const int32 HRowsB = M.Text.IsEmpty() ? 0 : UmPdRows(M.Text, Left, 16.0f, BodyTok, Measure);
      const float THB = 24.0f + (TRowsB - 1) * TitleLineSu;
      const float HHB = HRowsB > 0 ? 16.0f + (HRowsB - 1) * BodyLineSu : 0.0f;
      const float Row2 = FMath::Max(ButtonHSu, HHB);
      const float HB = FMath::Max(CompactMinHSu, 8.0f + THB + 4.0f + Row2 + 8.0f);
      if (HB < H) {
        P.TitleRows = TRowsB;
        P.HintRows = HRowsB;
        P.Panel = UmPdBox(X, Y, W, HB);
        const float Top = Y + 8.0f;
        if (IconW > 0.0f) P.Icon = UmPdBox(X + Pad, Top, 24.0f, 24.0f);
        const float Drawn = FMath::Min(TitleWB, FMath::CeilToFloat(Measure(M.Title, 24.0f, Heading)) + TextSlackSu);
        const float TitleBoxW = TRowsB > 1 ? TitleWB : Drawn;
        P.Title = UmPdBox(X + Pad + IconW, Top, TitleBoxW, THB);
        if (QueueW > 0.0f) P.Queue = UmPdBox(X + Pad + IconW + TitleBoxW + 8.0f, Top, QueueW, OrderChipSu);
        const float RowTop = Top + THB + 4.0f;
        if (HRowsB > 0) P.Hint = UmPdBox(X + Pad, RowTop + 0.5f * (Row2 - HHB), Left, HHB);
        PlaceButtons(X + W - Pad, RowTop + 0.5f * (Row2 - ButtonHSu));
        return P;
      }
    }
    P.Panel = UmPdBox(X, Y, W, H);
    const float TextTop = Y + 0.5f * (H - Inner);
    if (IconW > 0.0f) P.Icon = UmPdBox(X + Pad, TextTop, 24.0f, 24.0f);
    if (P.TitleRows > 0) {
      const float Drawn = FMath::Min(TitleW, FMath::CeilToFloat(Measure(M.Title, 24.0f, Heading)) + TextSlackSu);
      P.Title = UmPdBox(X + Pad + IconW, TextTop, P.TitleRows > 1 ? TitleW : Drawn, TH);
      if (QueueW > 0.0f) P.Queue = UmPdBox(X + Pad + IconW + (P.TitleRows > 1 ? TitleW : Drawn) + 8.0f, TextTop, QueueW, OrderChipSu);
    } else if (QueueW > 0.0f) {
      P.Queue = UmPdBox(X + Pad + IconW, TextTop, QueueW, OrderChipSu);
    }
    if (P.HintRows > 0) P.Hint = UmPdBox(X + Pad, TextTop + TH + (TH > 0.0f ? 4.0f : 0.0f), Left, HH);
    PlaceButtons(X + W - Pad, Y + 0.5f * (H - ButtonHSu));
    return P;
  }
  // class S (and BOOST anywhere): one row - glyph, card name, queue chip, buttons; the hint stays in STATUS
  // (ВР-VS2-HB34-13), except the hand-limit discard whose only text is its count
  const float Pad = 16.0f;
  const bool bHintRow = M.Title.IsEmpty() && !M.Text.IsEmpty() && !bBoost;
  const FString& RowText = bHintRow ? M.Text : M.Title;
  const float RowSize = bHintRow ? 16.0f : 24.0f;
  const FName RowTok = bHintRow ? BodyTok : Heading;
  float TextW = bBoost || RowText.IsEmpty() ? 0.0f : FMath::CeilToFloat(Measure(RowText, RowSize, RowTok)) + TextSlackSu;
  float Icon = bBoost ? 0.0f : IconW;
  auto Needed = [&]() {
    float N = 0.0f;
    int32 Parts = 0;
    for (const float C : {Icon > 0.0f ? 24.0f : 0.0f, TextW, QueueW, BW}) {
      if (C <= 0.0f) continue;
      N += C;
      ++Parts;
    }
    return N + FMath::Max(0, Parts - 1) * 8.0f + 2.0f * Pad;
  };
  if (Needed() > CompactLSu && Icon > 0.0f) Icon = 0.0f;  // the optional glyph goes first (HB-34 fix1)
  const float Min = bBoost ? 0.0f : (F.bClassS ? CompactSMinSu : CompactLSu);
  const float W = bBoost && !F.bClassS ? FMath::Max(560.0f, Needed()) : FMath::Clamp(Needed(), Min, CompactLSu);
  // a text that still does not fit wraps to more rows (never cut)
  const float TextRoom = TextW > 0.0f ? FMath::Max(1.0f, W - Needed() + TextW) : 0.0f;
  const int32 Rows = TextW > 0.0f ? UmPdRows(RowText, TextRoom, RowSize, RowTok, Measure) : 0;
  const float RowLine = bHintRow ? BodyLineSu : TitleLineSu;
  const float TH = Rows > 0 ? RowSize + (Rows - 1) * RowLine : 0.0f;
  const float H = FMath::Max(BW > 0.0f ? CompactMinHSu : 48.0f, TH + 16.0f);
  float X = 0.5f * (CW - W);
  if (F.bClassS && F.BandRightSu > F.BandLeftSu && (X < F.BandLeftSu || X + W > F.BandRightSu)) {
    X = FMath::Max(F.BandLeftSu, 0.5f * (F.BandLeftSu + F.BandRightSu - W));
  }
  const float Y = F.TopSu;
  P.Panel = UmPdBox(X, Y, W, H);
  float XX = X + Pad;
  if (Icon > 0.0f) {
    P.Icon = UmPdBox(XX, Y + 0.5f * (H - 24.0f), 24.0f, 24.0f);
    XX += 24.0f + 8.0f;
  }
  if (Rows > 0) {
    const float Drawn = FMath::Min(TextW, TextRoom);
    if (bHintRow) {
      P.Hint = UmPdBox(XX, Y + 0.5f * (H - TH), Drawn, TH);
      P.HintRows = Rows;
    } else {
      P.Title = UmPdBox(XX, Y + 0.5f * (H - TH), Drawn, TH);
      P.TitleRows = Rows;
    }
    XX += Drawn + 8.0f;
  }
  if (QueueW > 0.0f) P.Queue = UmPdBox(XX, Y + 0.5f * (H - OrderChipSu), QueueW, OrderChipSu);
  PlaceButtons(X + W - Pad, Y + 0.5f * (H - ButtonHSu));
  return P;
}

FString SourceName(const FS08PendingEffect& Head, const TArray<FS09CardView>& Known, const TMap<FString, FString>& HeroNames,
                   const TArray<FS09CardView>& OwnerDiscard, bool bRu, FString* OutText) {
  if (OutText) OutText->Reset();
  FString Id = Head.Id;
  Id.RemoveFromStart(TEXT("discard-choice-"));
  if (Id.StartsWith(TEXT("ability-"))) {
    // a hero ability (generic-hero-ability.handler: ability-<hero>-<kind>-p<n>): the owner's hero, as the data names it
    const FString* Hero = HeroNames.Find(Head.PlayerId);
    return Hero ? *Hero : FString();
  }
  auto Name = [bRu](const FS09CardView& C) { return bRu && !C.NameRu.IsEmpty() ? C.NameRu : C.Name; };
  // the effect id is "<catalog card id>-<field>-<i>..." (game-initialization.service: effects of card.id); the deck
  // lists name every catalog card, the instance ids "<catalog id>::<copy>" prefix nothing of it
  const FS09CardView* Best = nullptr;
  int32 BestLen = 0;
  for (const FS09CardView& C : Known) {
    if (C.bHidden || C.Name.IsEmpty()) continue;
    for (const FString* Key : {&C.CardId, &C.InstanceId}) {
      if (Key->Len() > BestLen && Id.StartsWith(*Key + TEXT("-"))) {
        Best = &C;
        BestLen = Key->Len();
      }
    }
  }
  if (Best) {
    if (OutText) *OutText = Best->Text;
    return Name(*Best);
  }
  // the text fallback (S09OpponentView::EffectCardName's rule): the owner's newest discard card holding the head's text
  const FString Needle = Head.Text.TrimStartAndEnd();
  if (!Needle.IsEmpty()) {
    for (int32 I = OwnerDiscard.Num() - 1; I >= 0; --I) {
      const FS09CardView& C = OwnerDiscard[I];
      if (!C.bHidden && !C.Name.IsEmpty() && C.Text.Contains(Needle, ESearchCase::IgnoreCase)) {
        if (OutText) *OutText = C.Text;
        return Name(C);
      }
    }
  }
  return FString();
}

FUmPendingModel Gather(const FUmPendingInput& In) {
  FUmPendingModel M;
  M.BusyWhy = In.BusyWhy;
  if (!In.bLive || !In.Ui) return M;
  const FS09CommandUi& Ui = *In.Ui;
  auto Count = [](int32 Need, int32 Have) {
    return FS09Reason::Make(TEXT("why.pick.count")).Arg(TEXT("need"), Need).Arg(TEXT("have"), Have);
  };
  auto Busy = [&In](const FS09Reason& Why) { return In.BusyWhy.IsSet() ? In.BusyWhy : Why; };
  // ---- the hand limit (not a pending effect): «Сбросьте {n}: выбрано {h}/{n}», no cancel ----
  if (Ui.Mode == ES09CommandMode::DiscardDraft) {
    if (In.bHeldBySlot) return M;
    const int32 Need = Ui.PendingDiscard.Count;
    const int32 Have = Ui.DiscardSelection.Num();
    M.View = EUmPendingView::Compact;
    M.Compact = EUmPendingCompact::Discard;
    M.Kind = TEXT("LIMIT");
    FFormatNamedArguments A;
    A.Add(TEXT("n"), FText::AsNumber(Need));
    A.Add(TEXT("h"), FText::AsNumber(Have));
    M.Text = UmPdString(TEXT("hud.pending.discard.count"), &A);
    M.bConfirm = true;
    M.ConfirmKey = TEXT("hud.number.confirm");
    M.ConfirmWhy = Busy(Have == Need ? FS09Reason()
                                     : FS09Reason::Make(TEXT("why.discard.count")).Arg(TEXT("need"), Need).Arg(TEXT("have"), Have));
    return M;
  }
  // ---- King Arthur's ability (SD-56): «Добавить BOOST?» - the question is in STATUS, here its two buttons ----
  if (Ui.Mode == ES09CommandMode::AttackDraft && Ui.IsAttackAbilityPromptOpen()) {
    M.View = EUmPendingView::Compact;
    M.Compact = EUmPendingCompact::Boost;
    M.Kind = TEXT("ABILITY");
    M.bConfirm = true;
    M.ConfirmKey = TEXT("ms.btn.boost.attack");
    M.ConfirmWhy = Busy(Ui.AttackAbilityBoostCardId.IsEmpty() ? Count(1, 0) : FS09Reason());
    M.bSecondary = true;
    M.SecondaryKey = TEXT("ms.btn.noboost");
    return M;
  }
  const FS08PendingEffect* QueueHead = Ui.PendingQueue.Num() > 0 ? &Ui.PendingQueue[0] : nullptr;
  // ---- my own head ----
  if (Ui.Mode == ES09CommandMode::PendingChoice && Ui.bHasPendingChoice) {
    const FS08PendingEffect& H = Ui.PendingChoice;
    if (In.bHeldBySlot) return M;
    FString SourceText;
    M.HeadId = H.Id;
    M.Kind = H.Type;
    M.Title = SourceName(H, In.Known, In.HeroNames, In.OwnerDiscard, In.bRu, &SourceText);
    const FString Printed = SourceText.TrimStartAndEnd().IsEmpty() ? H.Text.TrimStartAndEnd() : SourceText.TrimStartAndEnd();
    for (int32 I = 1; I < Ui.PendingQueue.Num(); ++I) {
      if (Ui.PendingQueue[I].PlayerId == In.ViewerId) ++M.QueueMore;
    }
    if (In.bCombatStaging) {
      M.View = EUmPendingView::AfterCombat;
      M.Text = UmPdString(TEXT("hud.pending.after.combat"));
      M.QueueMore = 0;
      return M;
    }
    const bool bPresenter = In.Presenter && In.Presenter->IsOpen() && In.Presenter->HeadId == H.Id;
    if (bPresenter && In.Presenter->bCollapsed) {
      M.View = EUmPendingView::Collapsed;
      FFormatNamedArguments A;
      A.Add(TEXT("card"), FText::FromString(M.Title.IsEmpty() ? H.Type : M.Title));
      M.Text = UmPdString(TEXT("hud.pending.collapsed"), &A);
      M.QueueMore = 0;
      return M;
    }
    if (bPresenter && In.Presenter->Present == ES09PendingPresent::Toast) {
      M.View = EUmPendingView::Toast;
      FFormatNamedArguments A;
      A.Add(TEXT("choice"), FText::FromString(In.RememberedChoice));
      M.Text = In.RememberedChoice.IsEmpty() ? FString() : UmPdString(TEXT("ms.pending.remembered"), &A);
      M.QueueMore = 0;
      return M;
    }
    M.bDecline = H.bOptional;
    M.bCollapse = true;
    M.ConfirmKey = TEXT("hud.number.confirm");
    const FString& T = H.Type;
    if (T == TEXT("CHOOSE_ONE")) {
      M.View = EUmPendingView::Modal;
      M.Body = EUmPendingBody::Options;
      M.Text = Printed;
      for (const FS08PendingOption& O : H.Options) M.Options.Add(O.Label);
      M.Selected = Ui.PendingOptionIndex;
      M.bConfirm = true;
      M.ConfirmWhy = Busy(M.Selected >= 0 ? FS09Reason() : Count(1, 0));
      M.bBack = M.Selected >= 0 && !In.BusyWhy.IsSet();
    } else if (T == TEXT("DECK_TOP_PICK")) {
      const bool bOrder = H.Mode == TEXT("ORDER");
      M.View = EUmPendingView::Modal;
      M.Body = bOrder ? EUmPendingBody::Order : EUmPendingBody::Pick;
      M.Text = Printed;
      M.HeroSlug = In.OwnHeroSlug;
      for (const FS09CardView& C : In.Revealed) {
        FUmPendingCard Card;
        Card.Card = C;
        const int32 At = Ui.PendingCardIds.IndexOfByKey(C.InstanceId);
        Card.bMarked = !bOrder && At != INDEX_NONE;
        Card.Order = bOrder && At != INDEX_NONE ? At + 1 : 0;
        M.Cards.Add(Card);
        if (M.Cards.Num() >= MaxCards) break;
      }
      M.PickNeed = In.PickNeed > 0 ? In.PickNeed : (bOrder ? M.Cards.Num() : (H.bHasValue ? H.Value : 2));
      M.PickHave = Ui.PendingCardIds.Num();
      M.bConfirm = true;
      M.ConfirmWhy = Busy(M.PickHave == M.PickNeed ? FS09Reason() : Count(M.PickNeed, M.PickHave));
    } else if (T == TEXT("MOVE") || T == TEXT("PLACE")) {
      M.View = EUmPendingView::Compact;
      M.Compact = EUmPendingCompact::Board;
      M.Icon = FName(T == TEXT("MOVE") ? TEXT("state-pending-move") : TEXT("state-pending-place"));
      M.Text = In.MovePrompt.IsSet() ? UmHudStatus::LineText(In.MovePrompt, FS09TurnStatusInput()).ToString() : Printed;
      M.bStay = T == TEXT("MOVE") && In.bCanStay;
    } else if (T == TEXT("TARGET_FIGHTER")) {
      M.View = EUmPendingView::Compact;
      M.Compact = EUmPendingCompact::Board;
      M.Text = Printed;
    } else if (T == TEXT("CHOOSE_SPACE")) {
      M.View = EUmPendingView::Compact;
      M.Compact = EUmPendingCompact::Board;
      M.Icon = FName(TEXT("state-pending-place"));
      M.Text = FirstSentence(Printed);
    } else if (T == TEXT("DISCARD_CARDS")) {
      M.View = EUmPendingView::Compact;
      M.Compact = EUmPendingCompact::Discard;
      const int32 Need = In.PickNeed > 0 ? In.PickNeed : (H.bHasValue ? H.Value : 1);
      const int32 Have = Ui.PendingCardIds.Num();
      FFormatNamedArguments A;
      A.Add(TEXT("n"), FText::AsNumber(Need));
      A.Add(TEXT("h"), FText::AsNumber(Have));
      M.Text = UmPdString(TEXT("hud.pending.discard.count"), &A);
      M.bConfirm = true;
      M.ConfirmWhy = Busy(Have == Need ? FS09Reason()
                                       : FS09Reason::Make(TEXT("why.discard.count")).Arg(TEXT("need"), Need).Arg(TEXT("have"), Have));
      M.bCollapse = false;  // HB-34 discard: «Подтвердить» only (C still collapses)
    } else if (T == TEXT("BOOST_CHOICE")) {
      M.View = EUmPendingView::Compact;
      M.Compact = EUmPendingCompact::HandPick;
      M.Text = Printed;
      M.bConfirm = true;
      M.ConfirmWhy = Busy(Ui.PendingCardIds.Num() == 1 ? FS09Reason() : Count(1, Ui.PendingCardIds.Num()));
    } else {
      // a type this client does not know a form for: the modal with its text (the server's own prompt)
      M.View = EUmPendingView::Modal;
      M.Body = EUmPendingBody::Text;
      M.Text = Printed;
      M.bConfirm = true;
      M.ConfirmWhy = Busy(FS09Reason());
    }
    return M;
  }
  // ---- the opponent's head: grey, the source card; the line only when STATUS does not say it already ----
  if (QueueHead && !QueueHead->PlayerId.IsEmpty() && QueueHead->PlayerId != In.ViewerId) {
    M.View = EUmPendingView::Opp;
    M.HeadId = QueueHead->Id;
    M.Kind = QueueHead->Type;
    M.Title = SourceName(*QueueHead, In.Known, In.HeroNames, In.OwnerDiscard, In.bRu);
    M.Text = In.bStatusSaysOpp ? FString() : UmPdString(TEXT("why.wait.opponent.choice"));
    if (M.Title.IsEmpty() && M.Text.IsEmpty()) return FUmPendingModel();
    M.BusyWhy.Reset();
    return M;
  }
  return M;
}
}  // namespace UmHudPending

// ------------------------------------------------------------------------------------------------ the widget

namespace {
template <typename T>
T* UmPdFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

void UmPdPlace(UWidget* W, const FBox2D& Box, int32 Z = 0) {
  UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr;
  if (!S || !Box.bIsValid) return;
  S->SetAnchors(FAnchors(0.0f, 0.0f));
  S->SetAlignment(FVector2D::ZeroVector);
  S->SetAutoSize(false);
  S->SetPosition(Box.Min);
  S->SetSize(Box.GetSize());
  S->SetZOrder(Z);
}

void UmPdShow(UWidget* W, bool bOn, ESlateVisibility On = ESlateVisibility::HitTestInvisible) {
  if (!W) return;
  const ESlateVisibility Want = bOn ? On : ESlateVisibility::Collapsed;
  if (W->GetVisibility() != Want) W->SetVisibility(Want);
}

void UmPdStyle(UTextBlock* T, FName Type, FName Color) {
  if (!T) return;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  T->SetFont(Theme.Font(Type));
  T->SetColorAndOpacity(FSlateColor(Theme.Color(Color)));
  T->SetShadowOffset(FVector2D::ZeroVector);
}

/** One line at the em SizeSu, measured at the scale it is drawn at (DPI x UI scale): the shaped glyphs of a scaled text
 *  run wider than the same text measured at 1 and divided (VS-4 gallery: «ОСТАВИТЬ НА МЕСТЕ» touched its button at
 *  1.125 px per su) - the plan sizes by the drawn width. */
float UmPdMeasureAt(const FString& Text, float SizeSu, FName Token, float PxPerSu) {
  if (Text.IsEmpty()) return 0.0f;
  if (!FSlateApplication::IsInitialized() || !FSlateApplication::Get().GetRenderer()) return UmDeckRow::MeasureSu(Text, SizeSu, Token);
  FSlateFontInfo Font = UUmHudTheme::Get().Font(Token);
  Font.Size = UmHudTheme::PointsFromSu(SizeSu);
  const float Scale = PxPerSu > 0.0f ? PxPerSu : 1.0f;
  const TSharedRef<FSlateFontMeasure> M = FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
  return static_cast<float>(M->Measure(Text, Font, Scale).X) / Scale;
}
}  // namespace

UClass* UUmHudPending::WidgetClass() { return UmGameHudSlots::WbpOrNative(UUmHudPending::StaticClass(), WidgetBlueprintPath); }

bool UUmHudPending::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  UCanvasPanel* RootW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Root")));
  RootW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(RootW, nullptr)) return Fail(TEXT("Root"));
  auto Text = [&Tree](const TCHAR* Name) {
    UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
    T->SetVisibility(ESlateVisibility::Collapsed);
    return T;
  };
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  auto Button = [&Tree, ButtonClass](const TCHAR* Name) {
    UUmButton* B = Tree.ConstructWidget<UUmButton>(ButtonClass, FName(Name));
    B->SetVisibility(ESlateVisibility::Collapsed);
    return B;
  };
  UBorder* PanelW = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("Panel")));
  PanelW->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(PanelW, RootW)) return Fail(TEXT("Panel"));
  // the plate click of the collapsed / toast forms (a flat button: nothing at rest, the hover skin on hover)
  if (!Attach(Button(TEXT("ExpandButton")), RootW)) return Fail(TEXT("ExpandButton"));
  UImage* EdgeW = Tree.ConstructWidget<UImage>(UImage::StaticClass(), FName(TEXT("Edge")));
  EdgeW->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(EdgeW, RootW)) return Fail(TEXT("Edge"));
  UCanvasPanel* HeaderW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Header")));
  HeaderW->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(HeaderW, RootW)) return Fail(TEXT("Header"));
  US08AnimatedIconWidget* IconW = Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(TEXT("HeaderIcon")));
  IconW->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(IconW, HeaderW)) return Fail(TEXT("HeaderIcon"));
  UTextBlock* Name = Text(TEXT("SourceName"));
  Name->SetAutoWrapText(true);
  if (!Attach(Name, HeaderW)) return Fail(TEXT("SourceName"));
  UBorder* Chip = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("QueueChip")));
  Chip->SetVisibility(ESlateVisibility::Collapsed);
  Chip->SetHorizontalAlignment(HAlign_Center);
  Chip->SetVerticalAlignment(VAlign_Center);
  if (!Attach(Chip, HeaderW)) return Fail(TEXT("QueueChip"));
  UTextBlock* ChipText = Text(TEXT("QueueText"));
  ChipText->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(ChipText, Chip)) return Fail(TEXT("QueueText"));
  UTextBlock* HintW = Text(TEXT("Hint"));
  HintW->SetAutoWrapText(true);
  if (!Attach(HintW, RootW)) return Fail(TEXT("Hint"));
  // the body: a scroll box (4 su bar) > a size box of the content > its canvas
  UScrollBox* Scroll = Tree.ConstructWidget<UScrollBox>(UScrollBox::StaticClass(), FName(TEXT("Body")));
  Scroll->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(Scroll, RootW)) return Fail(TEXT("Body"));
  USizeBox* BoxW = Tree.ConstructWidget<USizeBox>(USizeBox::StaticClass(), FName(TEXT("BodyBox")));
  if (!Attach(BoxW, Scroll)) return Fail(TEXT("BodyBox"));
  UCanvasPanel* Canvas = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("BodyCanvas")));
  Canvas->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(Canvas, BoxW)) return Fail(TEXT("BodyCanvas"));
  UTextBlock* BodyTextW = Text(TEXT("BodyText"));
  BodyTextW->SetAutoWrapText(true);
  if (!Attach(BodyTextW, Canvas)) return Fail(TEXT("BodyText"));
  UVerticalBox* Opts = Tree.ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), FName(TEXT("Options")));
  Opts->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(Opts, Canvas)) return Fail(TEXT("Options"));
  for (int32 I = 0; I < UmHudPending::MaxOptions; ++I) {
    const FString N = FString::Printf(TEXT("Option%d"), I);
    if (!Attach(Button(*N), Opts)) return Fail(*N);
  }
  UUmNumberPicker* PickerW = Tree.ConstructWidget<UUmNumberPicker>(UUmNumberPicker::StaticClass(), FName(TEXT("Picker")));
  PickerW->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(PickerW, Canvas)) return Fail(TEXT("Picker"));
  for (int32 I = 0; I < UmHudPending::MaxCards; ++I) {
    const FString N = FString::Printf(TEXT("Card%d"), I);
    UUmCardWidget* C = Tree.ConstructWidget<UUmCardWidget>(UUmCardWidget::WidgetClass(), FName(*N));
    C->SetVisibility(ESlateVisibility::Collapsed);
    if (!Attach(C, Canvas)) return Fail(*N);
  }
  for (int32 I = 0; I < UmHudPending::MaxCards; ++I) {
    const FString N = FString::Printf(TEXT("OrderChip%d"), I);
    UBorder* O = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(*N));
    O->SetVisibility(ESlateVisibility::Collapsed);
    O->SetHorizontalAlignment(HAlign_Center);
    O->SetVerticalAlignment(VAlign_Center);
    O->SetPadding(FMargin(0.0f));
    if (!Attach(O, Canvas)) return Fail(*N);
    const FString TN = FString::Printf(TEXT("OrderText%d"), I);
    UTextBlock* OT = Text(*TN);
    OT->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (!Attach(OT, O)) return Fail(*TN);
  }
  if (!Attach(Text(TEXT("Counter")), RootW)) return Fail(TEXT("Counter"));
  for (const TCHAR* N : {TEXT("BackButton"), TEXT("StayButton"), TEXT("DeclineButton"), TEXT("ConfirmButton"),
                         TEXT("SecondaryButton"), TEXT("CollapseButton")}) {
    if (!Attach(Button(N), RootW)) return Fail(N);
  }
  for (int32 I = 0; I < 3; ++I) {
    const FString N = FString::Printf(TEXT("KeyChip%d"), I);
    UBorder* K = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(*N));
    K->SetVisibility(ESlateVisibility::Collapsed);
    K->SetHorizontalAlignment(HAlign_Center);
    K->SetVerticalAlignment(VAlign_Center);
    if (!Attach(K, RootW)) return Fail(*N);
    const FString TN = FString::Printf(TEXT("KeyText%d"), I);
    UTextBlock* KT = Text(*TN);
    KT->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (!Attach(KT, K)) return Fail(*TN);
  }
  return true;
}

bool UUmHudPending::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  if (!WidgetTree->RootWidget) {
    FString Error;
    UWidgetTree* Tree = WidgetTree;
    bCodeDefaultTree = BuildDefaultTree(*Tree, [Tree](UWidget* Child, UPanelWidget* Parent) {
      if (!Parent) {
        Tree->RootWidget = Child;
        return true;
      }
      return Parent->AddChild(Child) != nullptr;
    }, &Error);
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD pending default tree: %s"), *Error);
  }
  UWidgetTree* T = WidgetTree;
  Root = UmPdFind<UCanvasPanel>(T, TEXT("Root"));
  Panel = UmPdFind<UBorder>(T, TEXT("Panel"));
  Edge = UmPdFind<UImage>(T, TEXT("Edge"));
  ExpandButton = UmPdFind<UUmButton>(T, TEXT("ExpandButton"));
  Header = UmPdFind<UCanvasPanel>(T, TEXT("Header"));
  HeaderIcon = UmPdFind<US08AnimatedIconWidget>(T, TEXT("HeaderIcon"));
  SourceName = UmPdFind<UTextBlock>(T, TEXT("SourceName"));
  QueueChip = UmPdFind<UBorder>(T, TEXT("QueueChip"));
  QueueText = UmPdFind<UTextBlock>(T, TEXT("QueueText"));
  Hint = UmPdFind<UTextBlock>(T, TEXT("Hint"));
  Body = UmPdFind<UScrollBox>(T, TEXT("Body"));
  BodyBox = UmPdFind<USizeBox>(T, TEXT("BodyBox"));
  BodyCanvas = UmPdFind<UCanvasPanel>(T, TEXT("BodyCanvas"));
  BodyText = UmPdFind<UTextBlock>(T, TEXT("BodyText"));
  Options = UmPdFind<UVerticalBox>(T, TEXT("Options"));
  Picker = UmPdFind<UUmNumberPicker>(T, TEXT("Picker"));
  Counter = UmPdFind<UTextBlock>(T, TEXT("Counter"));
  BackButton = UmPdFind<UUmButton>(T, TEXT("BackButton"));
  StayButton = UmPdFind<UUmButton>(T, TEXT("StayButton"));
  DeclineButton = UmPdFind<UUmButton>(T, TEXT("DeclineButton"));
  ConfirmButton = UmPdFind<UUmButton>(T, TEXT("ConfirmButton"));
  SecondaryButton = UmPdFind<UUmButton>(T, TEXT("SecondaryButton"));
  CollapseButton = UmPdFind<UUmButton>(T, TEXT("CollapseButton"));
  OptionPool.Reset();
  CardPool.Reset();
  ChipPool.Reset();
  ChipText.Reset();
  KeyPool.Reset();
  KeyText.Reset();
  for (int32 I = 0; I < UmHudPending::MaxOptions; ++I) OptionPool.Add(UmPdFind<UUmButton>(T, *FString::Printf(TEXT("Option%d"), I)));
  for (int32 I = 0; I < UmHudPending::MaxCards; ++I) {
    CardPool.Add(UmPdFind<UUmCardWidget>(T, *FString::Printf(TEXT("Card%d"), I)));
    ChipPool.Add(UmPdFind<UBorder>(T, *FString::Printf(TEXT("OrderChip%d"), I)));
    ChipText.Add(UmPdFind<UTextBlock>(T, *FString::Printf(TEXT("OrderText%d"), I)));
  }
  for (int32 I = 0; I < 3; ++I) {
    KeyPool.Add(UmPdFind<UBorder>(T, *FString::Printf(TEXT("KeyChip%d"), I)));
    KeyText.Add(UmPdFind<UTextBlock>(T, *FString::Printf(TEXT("KeyText%d"), I)));
  }
  // a WBP keeps neither the theme fonts nor the colours of the code tree: set at run time
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  UmPdStyle(SourceName, TEXT("type.heading"), TEXT("text.primary"));
  UmPdStyle(Hint, TEXT("type.body"), TEXT("text.primary"));
  UmPdStyle(BodyText, TEXT("type.body"), TEXT("text.primary"));
  UmPdStyle(Counter, TEXT("type.tag"), TEXT("text.primary"));
  UmPdStyle(QueueText, TEXT("type.tag"), TEXT("text.primary"));
  if (Counter) Counter->SetVisibility(ESlateVisibility::Collapsed);
  for (UTextBlock* K : KeyText) UmPdStyle(K, TEXT("type.tag"), TEXT("text.primary"));
  for (UBorder* K : KeyPool) {
    if (K) {
      if (const FSlateBrush* Skin = Theme.Skin(TEXT("key.chip"))) K->SetBrush(*Skin);
      K->SetPadding(FMargin(6.0f, 0.0f));
    }
  }
  for (int32 I = 0; I < ChipText.Num(); ++I) {
    // ВР-VS2-HB34-19: the order number - font.card 20 su card.navy on a card.glyph chip with a mark.keyline 1 su edge
    if (UTextBlock* O = ChipText[I]) {
      FSlateFontInfo Font = Theme.Font(TEXT("font.card"));
      Font.Size = UmHudTheme::PointsFromSu(20.0f);
      O->SetFont(Font);
      O->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("card.navy"))));
      O->SetShadowOffset(FVector2D::ZeroVector);
    }
    if (UBorder* C = ChipPool[I]) {
      C->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("card.glyph")), 0.5f * UmHudPending::OrderChipSu, Theme.Color(TEXT("mark.keyline")), 1.0f));
    }
  }
  if (QueueChip) {
    if (const FSlateBrush* Skin = Theme.Skin(TEXT("chip"))) QueueChip->SetBrush(*Skin);
    QueueChip->SetPadding(FMargin(6.0f, 0.0f));
  }
  if (Body) {
    // the 4 su bar of the modal body (HB-34: the ProgressTrack look); no shadows at the scrolled edges
    FScrollBarStyle Bar = Body->GetWidgetBarStyle();
    if (const FSlateBrush* Track = Theme.Skin(TEXT("progress.track"))) Bar.SetVerticalBackgroundImage(*Track);
    if (const FSlateBrush* Thumb = Theme.Skin(TEXT("progress.fill"))) {
      Bar.SetNormalThumbImage(*Thumb);
      Bar.SetHoveredThumbImage(*Thumb);
      Bar.SetDraggedThumbImage(*Thumb);
    }
    Bar.SetVerticalTopSlotImage(FSlateNoResource());
    Bar.SetVerticalBottomSlotImage(FSlateNoResource());
    Bar.SetThickness(UmHudPending::ScrollBarSu);
    Body->SetWidgetBarStyle(Bar);
    FScrollBoxStyle Box = Body->GetWidgetStyle();
    Box.SetTopShadowBrush(FSlateNoResource());
    Box.SetBottomShadowBrush(FSlateNoResource());
    Box.SetLeftShadowBrush(FSlateNoResource());
    Box.SetRightShadowBrush(FSlateNoResource());
    Body->SetWidgetStyle(Box);
    Body->SetScrollbarThickness(FVector2D(UmHudPending::ScrollBarSu));
    Body->SetScrollbarPadding(FMargin(0.0f));
    Body->SetAlwaysShowScrollbar(false);
  }
  for (UUmCardWidget* C : CardPool) {
    if (!C) continue;
    TWeakObjectPtr<UUmHudPending> WeakThis(this);
    TWeakObjectPtr<UUmCardWidget> WeakCard(C);
    C->SetOnInspect([WeakThis, WeakCard]() {
      UUmHudPending* Self = WeakThis.Get();
      UUmCardWidget* Card = WeakCard.Get();
      if (Self && Card && Self->Callbacks.OnInspect) Self->Callbacks.OnInspect(Card->GetCard());
    });
  }
  if (Root) Root->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  SetVisibility(ESlateVisibility::Collapsed);
  return bFirst;
}

bool UUmHudPending::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Header) Missing.Add(TEXT("Header"));
  if (!SourceName) Missing.Add(TEXT("SourceName"));
  if (!Body) Missing.Add(TEXT("Body"));
  if (!Options) Missing.Add(TEXT("Options"));
  if (!Picker) Missing.Add(TEXT("Picker"));
  if (!CollapseButton) Missing.Add(TEXT("CollapseButton"));
  if (!BackButton) Missing.Add(TEXT("BackButton"));
  if (!DeclineButton) Missing.Add(TEXT("DeclineButton"));
  if (!QueueChip) Missing.Add(TEXT("QueueChip"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

FString UUmHudPending::WidgetSourceName() const {
  return bCodeDefaultTree ? FString(TEXT("code-default")) : GetClass()->GetPathName();
}

UUmCardWidget* UUmHudPending::GetCard(int32 Index) const { return CardPool.IsValidIndex(Index) ? CardPool[Index].Get() : nullptr; }

UUmButton* UUmHudPending::GetOption(int32 Index) const { return OptionPool.IsValidIndex(Index) ? OptionPool[Index].Get() : nullptr; }

void UUmHudPending::SetSyncLoad(bool bOn) {
  for (UUmCardWidget* C : CardPool) {
    if (C) C->SetSyncLoad(bOn);
  }
}

void UUmHudPending::SetClockOverrideMs(double Ms) {
  for (UUmCardWidget* C : CardPool) {
    if (C) C->SetClockOverrideMs(Ms);
  }
  if (HeaderIcon) HeaderIcon->SetClockOverrideMs(Ms >= 0.0 ? static_cast<float>(Ms) : -1.0f);
}

void UUmHudPending::SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FCallbacks InCallbacks) {
  Arbiter = InArbiter;
  Callbacks = MoveTemp(InCallbacks);
  TWeakObjectPtr<UUmHudPending> WeakThis(this);
  using FFn = TFunction<void(const FS09HudPressOutcome&)> FCallbacks::*;
  auto Bind = [&InArbiter, WeakThis](UUmButton* B, const TCHAR* Id, FFn Member) {
    if (!B) return;
    B->SetPress(FName(Id), InArbiter, FS09OnHudPressOutcome::CreateLambda([WeakThis, Member](const FS09HudPressOutcome& O) {
      UUmHudPending* Self = WeakThis.Get();
      if (Self && (Self->Callbacks.*Member)) (Self->Callbacks.*Member)(O);
    }));
  };
  // own element ids: the Slate panel (-S09Markers) keeps its hud.pending.* ids beside these
  Bind(ConfirmButton, TEXT("pending.um.confirm"), &FCallbacks::OnConfirm);
  Bind(SecondaryButton, TEXT("pending.um.secondary"), &FCallbacks::OnSecondary);
  Bind(StayButton, TEXT("pending.um.stay"), &FCallbacks::OnStay);
  Bind(DeclineButton, TEXT("pending.um.decline"), &FCallbacks::OnDecline);
  Bind(BackButton, TEXT("pending.um.back"), &FCallbacks::OnBack);
  Bind(CollapseButton, TEXT("pending.um.collapse"), &FCallbacks::OnToggle);
  Bind(ExpandButton, TEXT("pending.um.expand"), &FCallbacks::OnToggle);
  for (int32 I = 0; I < OptionPool.Num(); ++I) {
    if (UUmButton* B = OptionPool[I]) {
      B->SetPress(FName(*FString::Printf(TEXT("pending.um.option.%d"), I)), InArbiter,
                  FS09OnHudPressOutcome::CreateLambda([WeakThis, I](const FS09HudPressOutcome& O) {
                    UUmHudPending* Self = WeakThis.Get();
                    if (Self && Self->Callbacks.OnOption) Self->Callbacks.OnOption(O, I);
                  }));
    }
  }
  if (Picker) {
    Picker->SetInput(InArbiter,
                     [WeakThis](const FS09HudPressOutcome& O, int32 Delta) {
                       UUmHudPending* Self = WeakThis.Get();
                       if (Self && Self->Callbacks.OnStep) Self->Callbacks.OnStep(O, Delta);
                     },
                     [WeakThis](const FS09HudPressOutcome& O) {
                       UUmHudPending* Self = WeakThis.Get();
                       if (Self && Self->Callbacks.OnConfirm) Self->Callbacks.OnConfirm(O);
                     },
                     [WeakThis](const FS09HudPressOutcome& O) {
                       UUmHudPending* Self = WeakThis.Get();
                       if (Self && Self->Callbacks.OnBack) Self->Callbacks.OnBack(O);
                     });
  }
}

void UUmHudPending::SetFrame(const FUmPendingFrame& InFrame) {
  if (bHasFrame && Frame == InFrame) return;
  Frame = InFrame;
  bHasFrame = true;
  if (bHasModel) Relayout();
}

void UUmHudPending::ApplyModel(const FUmPendingModel& InModel) {
  if (bHasModel && Model == InModel) return;
  Model = InModel;
  bHasModel = true;
  Relayout();
  // the change line (no names, no texts): the form, the kind, the head and what the buttons do
  const FString Key = FString::Printf(TEXT("view=%s kind=%s head=%s body=%s queue=%d pick=%d/%d sel=%d"),
                                      Model.View == EUmPendingView::Hidden ? TEXT("hidden") : UmHudPending::ViewName(Model.View),
                                      Model.Kind.IsEmpty() ? TEXT("-") : *Model.Kind, Model.HeadId.IsEmpty() ? TEXT("-") : *Model.HeadId,
                                      Model.View == EUmPendingView::Modal ? UmHudPending::BodyName(Model.Body) : TEXT("-"),
                                      Model.QueueMore, Model.PickHave, Model.PickNeed, Model.Selected);
  if (Key != LastChangeKey) {
    LastChangeKey = Key;
    bChangePending = true;
  }
}

FString UUmHudPending::TakeChangeLine() {
  if (!bChangePending) return FString();
  bChangePending = false;
  return TEXT("HUD-PENDING ") + LastChangeKey + (Model.View == EUmPendingView::AfterCombat ? TEXT(" wait=combat") : TEXT(""));
}

FName UUmHudPending::PanelSkin() const {
  switch (Model.View) {
    case EUmPendingView::Modal: return FName(TEXT("modal"));
    case EUmPendingView::Toast: return FName(TEXT("toast"));
    default: return FName(TEXT("panel"));
  }
}

FBox2D UUmHudPending::PanelRectSu() const { return Model.View == EUmPendingView::Hidden ? FBox2D(ForceInit) : PlanNow.Panel; }

void UUmHudPending::Relayout() {
  using namespace UmHudPending;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (Model.View == EUmPendingView::Hidden || !bHasFrame) {
    SetVisibility(ESlateVisibility::Collapsed);
    PlanNow = FUmPendingPlan();
    return;
  }
  SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  // ---- the labels as drawn (the plan measures them) ----
  LabelsNow.Reset();
  LabelsNow.Add(FName(TEXT("Back")), UmPdString(TEXT("hud.pending.back")));
  LabelsNow.Add(FName(TEXT("Decline")), UmPdString(TEXT("ms.btn.decline")));
  LabelsNow.Add(FName(TEXT("Stay")), UmPdString(TEXT("ms.btn.stay")));
  LabelsNow.Add(FName(TEXT("Collapse")), UmPdString(TEXT("ms.btn.collapse")));
  LabelsNow.Add(FName(TEXT("Confirm")), UmPdString(Model.ConfirmKey.IsEmpty() ? FString(TEXT("hud.number.confirm")) : Model.ConfirmKey));
  if (!Model.SecondaryKey.IsEmpty()) LabelsNow.Add(FName(TEXT("Secondary")), UmPdString(Model.SecondaryKey));
  {
    FFormatNamedArguments A;
    A.Add(TEXT("k"), FText::AsNumber(Model.PickHave));
    A.Add(TEXT("n"), FText::AsNumber(Model.PickNeed));
    LabelsNow.Add(FName(TEXT("Counter")), UmPdString(TEXT("hud.pending.pick.count"), &A));
    FFormatNamedArguments Q;
    Q.Add(TEXT("k"), FText::AsNumber(Model.QueueMore));
    LabelsNow.Add(FName(TEXT("Queue")), UmPdString(TEXT("hud.pending.queue"), &Q));
  }
  LabelsNow.Add(FName(TEXT("KeyEnter")), UmPdString(TEXT("hud.key.confirm")));
  LabelsNow.Add(FName(TEXT("KeyX")), UmPdString(TEXT("hud.key.decline")));
  LabelsNow.Add(FName(TEXT("KeyC")), UmPdString(TEXT("hud.key.collapse")));
  const float MeasurePx = Frame.PxPerSu;
  PlanNow = Plan(Model, Frame, LabelsNow, [MeasurePx](const FString& T, float S, FName Tok) { return UmPdMeasureAt(T, S, Tok, MeasurePx); });
  const FUmPendingPlan& P = PlanNow;
  const float Px = Frame.PxPerSu > 0.0f ? Frame.PxPerSu : 1.0f;
  const bool bGrey = Model.View == EUmPendingView::Opp || Model.View == EUmPendingView::AfterCombat;
  const FName TextColor = bGrey ? FName(TEXT("text.secondary")) : FName(TEXT("text.primary"));
  // ---- the plate and its edge: own - state.pending 2 su; grey - the panel skin's own panel.edge 1 su ----
  if (Panel) {
    if (const FSlateBrush* Skin = Theme.SkinFor(PanelSkin(), Px)) Panel->SetBrush(*Skin);
    UmPdShow(Panel, true);
    UmPdPlace(Panel, P.Panel, 0);
  }
  if (Edge) {
    const bool bOwnEdge = !bGrey && Model.View != EUmPendingView::Toast;
    UmPdShow(Edge, bOwnEdge);
    if (bOwnEdge) {
      Edge->SetBrush(FSlateRoundedBoxBrush(FLinearColor::Transparent, Theme.RadiusSu(TEXT("radius.l")), Theme.Color(TEXT("state.pending")), 2.0f));
      UmPdPlace(Edge, P.Panel, 1);
    }
  }
  // ---- the header: glyph, card name, queue chip ----
  const bool bHeader = P.Title.bIsValid || P.Icon.bIsValid || P.Queue.bIsValid;
  UmPdShow(Header, bHeader, ESlateVisibility::SelfHitTestInvisible);
  if (bHeader && Header) {
    FBox2D H = P.Panel;  // the header canvas covers the plate: its parts keep their canvas coordinates
    UmPdPlace(Header, H, 3);
    const FVector2D O = H.Min;
    auto Local = [&O](const FBox2D& B) { return FBox2D(B.Min - O, B.Max - O); };
    UmPdShow(HeaderIcon, P.Icon.bIsValid);
    if (P.Icon.bIsValid && HeaderIcon) {
      if (HeaderIcon->GetIconId() != Model.Icon && HeaderIcon->SetIcon(Model.Icon, 24.0f, 24)) {
        HeaderIcon->SetDisplaySizeSu(24.0f);
        HeaderIcon->ShowAtRest();
      }
      UmPdPlace(HeaderIcon, Local(P.Icon), 1);
    }
    UmPdShow(SourceName, P.Title.bIsValid);
    if (P.Title.bIsValid && SourceName) {
      const bool bModal = Model.View == EUmPendingView::Modal;
      const bool bToast = Model.View == EUmPendingView::Toast;
      FSlateFontInfo Font = Theme.Font(bModal ? TEXT("type.title") : bToast ? TEXT("type.body") : TEXT("type.heading"));
      if (bToast) Font.TypefaceFontName = Theme.Font(TEXT("type.heading")).TypefaceFontName;  // the toast's bold source
      SourceName->SetFont(Font);
      SourceName->SetColorAndOpacity(FSlateColor(Theme.Color(TextColor)));
      SourceName->SetText(FText::FromString(Model.Title));
      SourceName->SetWrapTextAt(static_cast<float>(P.Title.GetSize().X) + 2.0f);
      UmPdPlace(SourceName, Local(P.Title), 1);
    }
    UmPdShow(QueueChip, P.Queue.bIsValid);
    if (P.Queue.bIsValid) {
      if (QueueText) QueueText->SetText(FText::FromString(LabelsNow.FindRef(FName(TEXT("Queue")))));
      UmPdPlace(QueueChip, Local(P.Queue), 2);
    }
  }
  // ---- the hint / grey line / toast line / collapsed text ----
  UmPdShow(Hint, P.Hint.bIsValid);
  if (P.Hint.bIsValid && Hint) {
    Hint->SetColorAndOpacity(FSlateColor(Theme.Color(TextColor)));
    Hint->SetText(FText::FromString(Model.Text));
    Hint->SetWrapTextAt(static_cast<float>(P.Hint.GetSize().X) + 1.0f);
    // a one-row plate (collapsed) centres its line
    FBox2D B = P.Hint;
    if (Model.View == EUmPendingView::Collapsed) B = FBox2D(FVector2D(B.Min.X, B.Min.Y + 0.5 * (B.GetSize().Y - 20.0)), FVector2D(B.Max.X, B.Min.Y + 0.5 * (B.GetSize().Y + 20.0)));
    UmPdPlace(Hint, B, 3);
  }
  // ---- the modal body ----
  const bool bModal = Model.View == EUmPendingView::Modal;
  UmPdShow(Body, bModal, ESlateVisibility::Visible);
  if (bModal && Body) {
    UmPdPlace(Body, P.BodyView, 2);
    const float BodyW = static_cast<float>(P.BodyView.GetSize().X);
    if (BodyBox) {
      BodyBox->SetWidthOverride(BodyW);
      BodyBox->SetHeightOverride(P.ContentSu);
    }
    UmPdShow(BodyText, P.BodyTextSu > 0.0f);
    if (BodyText) {
      BodyText->SetText(FText::FromString(Model.Text));
      BodyText->SetWrapTextAt(BodyW - 8.0f);
      UmPdPlace(BodyText, FBox2D(FVector2D(0.0, 0.0), FVector2D(BodyW - 8.0f, P.BodyTextSu)), 0);
    }
    const float Lead = P.BodyTextSu > 0.0f ? P.BodyTextSu + 12.0f : 0.0f;
    const bool bOptions = Model.Body == EUmPendingBody::Options;
    UmPdShow(Options, bOptions, ESlateVisibility::SelfHitTestInvisible);
    if (bOptions && Options) {
      const int32 N = FMath::Min(Model.Options.Num(), OptionPool.Num());
      UmPdPlace(Options, FBox2D(FVector2D(0.0, Lead), FVector2D(BodyW - 8.0f, Lead + N * ButtonHSu + FMath::Max(0, N - 1) * ButtonGapSu)), 0);
      for (int32 I = 0; I < OptionPool.Num(); ++I) {
        UUmButton* B = OptionPool[I];
        if (!B) continue;
        const bool bOn = I < N;
        UmPdShow(B, bOn, ESlateVisibility::Visible);
        if (!bOn) continue;
        if (UVerticalBoxSlot* S = Cast<UVerticalBoxSlot>(B->Slot)) {
          S->SetHorizontalAlignment(HAlign_Fill);
          S->SetPadding(FMargin(0.0f, 0.0f, 0.0f, I + 1 < N ? ButtonGapSu : 0.0f));
        }
        FUmButtonModel O;
        O.Label = FText::FromString(Model.Options[I]);
        O.bSelected = Model.Selected == I;
        O.HeightSu = ButtonHSu;
        O.MinWidthSu = BodyW - 8.0f;
        O.Reason = Model.BusyWhy;
        O.bEnabled = !Model.BusyWhy.IsSet();
        B->ApplyModel(O);
      }
    }
    const bool bNumber = Model.Body == EUmPendingBody::Number;
    UmPdShow(Picker, bNumber, ESlateVisibility::SelfHitTestInvisible);
    if (bNumber && Picker) {
      FUmNumberModel NM = Model.Number;
      if (Model.BusyWhy.IsSet()) NM.ConfirmWhy = Model.BusyWhy;
      Picker->ApplyModel(NM, BodyW - 8.0f);
      UmPdPlace(Picker, FBox2D(FVector2D(0.0, Lead), FVector2D(BodyW - 8.0f, Lead + UmNumberPicker::HeightSu(!NM.Result.IsEmpty()))), 0);
    }
    // the 4 su bar only when the body scrolls (HB-34: «прокрутка только при превышении cap»)
    Body->SetScrollBarVisibility(P.ScrollSu > 0.5f ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
    Body->ScrollToStart();
  }
  ApplyCards();
  // ---- the counter (PICK) ----
  UmPdShow(Counter, P.Counter.bIsValid);
  if (P.Counter.bIsValid && Counter) {
    Counter->SetText(FText::FromString(LabelsNow.FindRef(FName(TEXT("Counter")))));
    FBox2D C = P.Counter;
    C = FBox2D(FVector2D(C.Min.X, C.Min.Y + 0.5 * (C.GetSize().Y - 20.0)), FVector2D(C.Max.X, C.Min.Y + 0.5 * (C.GetSize().Y + 20.0)));
    UmPdPlace(Counter, C, 3);
  }
  // ---- the key chips (toast, collapsed) ----
  for (int32 I = 0; I < KeyPool.Num(); ++I) {
    const bool bOn = P.Keys.IsValidIndex(I);
    UmPdShow(KeyPool[I], bOn);
    if (!bOn) continue;
    if (KeyText.IsValidIndex(I) && KeyText[I]) KeyText[I]->SetText(FText::FromString(P.Keys[I].Key));
    UmPdPlace(KeyPool[I], P.Keys[I].Value, 4);
  }
  ApplyButtons();
}

void UUmHudPending::ApplyCards() {
  using namespace UmHudPending;
  const bool bCards = Model.View == EUmPendingView::Modal && (Model.Body == EUmPendingBody::Pick || Model.Body == EUmPendingBody::Order);
  const float Px = Frame.PxPerSu > 0.0f ? Frame.PxPerSu : 1.0f;
  for (int32 I = 0; I < CardPool.Num(); ++I) {
    UUmCardWidget* C = CardPool[I];
    const bool bOn = bCards && Model.Cards.IsValidIndex(I) && PlanNow.Cards.IsValidIndex(I);
    UmPdShow(C, bOn, ESlateVisibility::Visible);
    const bool bChip = bOn && Model.Body == EUmPendingBody::Order && Model.Cards[I].Order > 0 && PlanNow.Chips.IsValidIndex(I);
    if (ChipPool.IsValidIndex(I)) UmPdShow(ChipPool[I], bChip);
    if (!bOn || !C) continue;
    const FUmPendingCard& Card = Model.Cards[I];
    FUmCardState S;
    S.Show = Frame.bClassS ? EUmCardShow::ClassSHand : EUmCardShow::Hand;
    S.HeroSlug = Model.HeroSlug;
    S.PxPerSu = Px;
    C->ApplyModel(Card.Card, S);
    // CP-17: the marked card - card.frame.selected 3 su (and raised 16 su, the plan); ORDER - a numbered one too
    C->SetSelected(Card.bMarked || Card.Order > 0);
    C->SetPlayable(true);
    const FString Id = Card.Card.InstanceId;
    TWeakObjectPtr<UUmHudPending> WeakThis(this);
    C->SetPress(FName(*(TEXT("pending.um.card.") + Id)), Arbiter, FS09OnHudPressOutcome::CreateLambda([WeakThis, Id](const FS09HudPressOutcome& O) {
      UUmHudPending* Self = WeakThis.Get();
      if (Self && Self->Callbacks.OnCard) Self->Callbacks.OnCard(O, Id);
    }));
    UmPdPlace(C, PlanNow.Cards[I], 1);
    if (bChip && ChipPool[I]) {
      if (ChipText.IsValidIndex(I) && ChipText[I]) ChipText[I]->SetText(FText::AsNumber(Card.Order));
      UmPdPlace(ChipPool[I], PlanNow.Chips[I], 2);
    }
  }
}

void UUmHudPending::ApplyButtons() {
  using namespace UmHudPending;
  struct FOne {
    UUmButton* B;
    FName Name;
    bool bPrimary;
  };
  const FOne All[] = {{BackButton, FName(TEXT("Back")), false},         {StayButton, FName(TEXT("Stay")), false},
                      {DeclineButton, FName(TEXT("Decline")), false},   {ConfirmButton, FName(TEXT("Confirm")), true},
                      {SecondaryButton, FName(TEXT("Secondary")), false}, {CollapseButton, FName(TEXT("Collapse")), false}};
  for (const FOne& One : All) {
    if (!One.B) continue;
    const FBox2D R = PlanNow.Find(One.Name);
    UmPdShow(One.B, R.bIsValid, ESlateVisibility::Visible);
    if (!R.bIsValid) continue;
    FUmButtonModel M;
    M.Variant = One.bPrimary ? EUmButtonVariant::Primary : EUmButtonVariant::Normal;
    M.Label = FText::FromString(LabelsNow.FindRef(One.Name));
    M.HeightSu = ButtonHSu;
    M.MinWidthSu = static_cast<float>(R.GetSize().X);
    FS09Reason Why = Model.BusyWhy;
    if (One.Name == FName(TEXT("Confirm")) && Model.ConfirmWhy.IsSet()) Why = Model.ConfirmWhy;
    if (One.Name == FName(TEXT("Collapse")) || One.Name == FName(TEXT("Back"))) Why.Reset();  // local: never refused
    M.Reason = Why;
    M.bEnabled = !Why.IsSet();
    One.B->ApplyModel(M);
    UmPdPlace(One.B, R, 5);
  }
  // the plate click of the collapsed plate and the toast
  const FBox2D Expand = PlanNow.Find(FName(TEXT("Expand")));
  UmPdShow(ExpandButton, Expand.bIsValid, ESlateVisibility::Visible);
  if (Expand.bIsValid && ExpandButton) {
    FUmButtonModel M;
    M.bFlat = true;
    M.HeightSu = static_cast<float>(Expand.GetSize().Y);
    M.MinWidthSu = static_cast<float>(Expand.GetSize().X);
    ExpandButton->ApplyModel(M);
    UmPdPlace(ExpandButton, Expand, 1);
  }
}

void UUmHudPending::CollectShotLines(TArray<FString>& Out) const {
  if (!bHasModel || Model.View == EUmPendingView::Hidden) return;
  const float Px = Frame.PxPerSu > 0.0f ? Frame.PxPerSu : 1.0f;
  const FBox2D R = PlanNow.Panel;
  FS08ScreenRect Rect;
  if (R.bIsValid) Rect = FS08ScreenRect(R.Min.X * Px, R.Min.Y * Px, R.Max.X * Px, R.Max.Y * Px);
  const bool bVisible = UmGameHudSlots::ShownByProperty(this) && R.bIsValid;
  TArray<FString> Names;
  for (const TPair<FName, FBox2D>& B : PlanNow.Buttons) Names.Add(B.Key.ToString().ToLower());
  const bool bGrey = Model.View == EUmPendingView::Opp || Model.View == EUmPendingView::AfterCombat;
  const FString Extra = FString::Printf(
      TEXT("kind=%s body=%s tone=%s wait=%s queue=%d pick=%d/%d sel=%d buttons=%s scroll=%.0f class=%s w=%.0f h=%.0f"),
      Model.Kind.IsEmpty() ? TEXT("-") : *Model.Kind, Model.View == EUmPendingView::Modal ? UmHudPending::BodyName(Model.Body) : TEXT("-"),
      bGrey ? TEXT("grey") : TEXT("own"), Model.View == EUmPendingView::AfterCombat ? TEXT("combat") : TEXT("-"), Model.QueueMore,
      Model.PickHave, Model.PickNeed, Model.Selected, Names.Num() ? *FString::Join(Names, TEXT(",")) : TEXT("-"), PlanNow.ScrollSu,
      Frame.bClassS ? TEXT("S") : TEXT("L"), R.bIsValid ? R.GetSize().X : 0.0, R.bIsValid ? R.GetSize().Y : 0.0);
  Out.Add(S08ArtHud::FormatWidgetLineEx(TEXT("UI-HUD-PENDING"), TEXT("umg"), UmHudPending::ViewName(Model.View), FString(), Rect,
                                        bVisible && !Rect.IsEmpty(), bVisible, WidgetSourceName(), Extra));
}
