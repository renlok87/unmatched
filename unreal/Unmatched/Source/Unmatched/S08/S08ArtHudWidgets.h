// W4-C hybrid HUD (user decision 2026-09-28): the ART-004 art HUD layer as
// UMG widget CLASSES ("panel = class", engine gate memo HUD row). C++ keeps
// the model/controller - data, placement geometry, traces, seq dedupe
// (S08ArtHud.h, AS08FlowGameMode) - and each widget only renders what it is
// given. Layout lives in a widget tree:
//   - WBP_S08ArtPlate / WBP_S08ArtIcon (/Game/S08/UI/ArtHud, children of these
//     classes) - the designer edits layout and the Style tokens there without
//     a C++ rebuild; the required parts are BindWidget properties, so a WBP
//     that loses one does not compile;
//   - the code default tree (BuildDefaultTree) when the class is used without
//     a designer tree (native class, or a WBP whose tree is empty). The WBP
//     authoring script builds its tree with the SAME function, so at port
//     time WBP == code default == the pre-UMG Slate plate (parity tests).
// No Property Binding: the controller pushes data on change only.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "S08ArtHudStyle.h"
#include "S08ArtHudText.h"
#include "S08ArtHudWidgets.generated.h"

class UBorder;
class UImage;
class UPanelWidget;
class USizeBox;
class UTextBlock;
class UTexture2D;
class UWidget;
class UWidgetTree;
class SWidget;

/** A traced widget part: gate id (S08ArtHudIds) + its Slate widget. */
struct FS08WidgetPart {
  FString Id;
  TSharedPtr<SWidget> Widget;
};

/** Attaches Child under Parent (nullptr = tree root). Native path: plain
 *  AddChild / RootWidget; WBP authoring path: FWidgetBlueprintOperationUtils
 *  (variable GUIDs, transactions). Returns false on failure. */
using FS08AttachWidget = TFunctionRef<bool(UWidget* Child, UPanelWidget* Parent)>;

/** Combat plate: name + team chip, HP bar + HP text, status line. */
UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API US08ArtPlateWidget : public UUserWidget {
  GENERATED_BODY()

public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/ArtHud/WBP_S08ArtPlate

  virtual bool Initialize() override;

  /** The pre-UMG Slate plate as a widget tree (names = BindWidget names). */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  /** Tokens -> bound widgets (colors via FLinearColor(FColor), fonts, sizes). */
  void ApplyStyle();
  /** Data push from the controller (on change only). */
  void ApplyTexts(const FS08PlateTexts& Texts);
  /** Every BindWidget part is bound (false = broken tree). */
  bool HasAllParts(FString* OutMissing = nullptr) const;
  void CollectParts(TArray<FS08WidgetPart>& Out) const;
  FVector2D GetPlateSizeSu() const { return Style.SizeSu; }
  /** "code-default" when the tree came from BuildDefaultTree at runtime. */
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }
  /** W5b-R: exact-size team shape textures (T_UI_TeamShape_Circle_12 / _Hex_12); tinted by the chip colour. */
  void SetTeamShapeBrushes(const FSlateBrush& Circle, const FSlateBrush& Hex);

  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD")
  FS08ArtHudPlateStyle Style;

  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<UBorder> PlateBackground;
  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<UImage> Marker;
  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<UTextBlock> NameText;
  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<UBorder> TeamChip;
  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<UTextBlock> TeamText;
  /** W5b-R D-3: team shape chip (circle P1 / hexagon P2) in the on-screen team colour. */
  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<UImage> TeamShape;
  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<USizeBox> HpBar;
  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<UImage> HpBack;
  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<USizeBox> HpFill;
  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<UImage> HpFillImage;
  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<UTextBlock> HpText;
  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<UTextBlock> StatusText;

protected:
  virtual void NativePreConstruct() override;

private:
  void ApplyDynamic();
  bool bCodeDefaultTree = false;
  bool bOwn = true;
  uint8 TeamSlot = 0;
  float HpFraction = 1.0f;
  FSlateBrush ShapeBrushes[2];
  bool bShapeBrushes = false;
};

/** W5b-R D-1: tag mode of a fighter's screen tag. */
enum class ES08TagMode : uint8 { Full, Compact, Hidden };
inline const TCHAR* S08TagModeName(ES08TagMode Mode) {
  return Mode == ES08TagMode::Full ? TEXT("full") : Mode == ES08TagMode::Compact ? TEXT("compact") : TEXT("hidden");
}

/** Everything a tag shows (already localized; the controller pushes it on change). */
struct FS08TagTexts {
  FText Name;
  FText Hp;
  float HpFraction = 0.0f;
  uint8 TeamSlot = 0;  // look slot: 0 = P1 circle, 1 = P2 hexagon
  ES08TagMode Mode = ES08TagMode::Compact;
};

/** W5b-R D-1 (proposal UI-HUD-TAG): screen tag of a fighter - team chip, name (full mode), HP mini bar + HP text on an
 *  opaque background. Replaces the world TextRender labels on the art board. */
UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API US08ArtTagWidget : public UUserWidget {
  GENERATED_BODY()

public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/ArtHud/WBP_S08ArtTag

  virtual bool Initialize() override;
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  void ApplyStyle();
  void ApplyModel(const FS08TagTexts& Texts);
  void SetTeamShapeBrushes(const FSlateBrush& Circle, const FSlateBrush& Hex);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  void CollectParts(TArray<FS08WidgetPart>& Out) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }
  int32 NameFontSize() const { return Style.NameFont.Size; }
  int32 HpFontSize() const { return Style.HpFont.Size; }

  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD")
  FS08ArtHudTagStyle Style;

  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<UBorder> TagBackground;
  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<USizeBox> ChipBox;
  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<UImage> TeamShape;
  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<UTextBlock> NameText;
  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<USizeBox> HpBar;
  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<UImage> HpBack;
  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<USizeBox> HpFill;
  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<UImage> HpFillImage;
  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<UTextBlock> HpText;

protected:
  virtual void NativePreConstruct() override;

private:
  void ApplyDynamic();
  bool bCodeDefaultTree = false;
  uint8 TeamSlot = 0;
  float HpFraction = 1.0f;
  ES08TagMode Mode = ES08TagMode::Compact;
  FSlateBrush ShapeBrushes[2];
  bool bShapeBrushes = false;
};

/** W5b-R D-1 (proposal UI-HUD-DAMAGE): the "-N" damage number capsule. */
UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API US08ArtDamageWidget : public UUserWidget {
  GENERATED_BODY()

public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/ArtHud/WBP_S08ArtDamage

  virtual bool Initialize() override;
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  void ApplyStyle();
  void ApplyAmount(const FText& Text);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  void CollectParts(TArray<FS08WidgetPart>& Out) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }
  int32 FontSize() const { return Style.Font.Size; }

  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD")
  FS08ArtHudDamageStyle Style;

  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<UBorder> DamageBackground;
  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<UTextBlock> DamageText;

protected:
  virtual void NativePreConstruct() override;

private:
  bool bCodeDefaultTree = false;
};

/** Desired size of a widget in slate units at layout scale 1 (SlatePrepass(1) on its Slate widget - also while it is
 *  collapsed, so the layout can size a tag before it is shown). */
UNMATCHED_API FVector2D S08ArtHudPrepassSize(UWidget& Widget);

/** Exact-size combat icon (24/32/48 px texture, no mips). */
UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API US08ArtIconWidget : public UUserWidget {
  GENERATED_BODY()

public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/ArtHud/WBP_S08ArtIcon

  virtual bool Initialize() override;
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  /** Same brush the Slate path draws: the texture at ImageSizeSu, no tiling. */
  void SetIconBrush(const FSlateBrush& Brush);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  void CollectParts(TArray<FS08WidgetPart>& Out) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }

  UPROPERTY(BlueprintReadOnly, Category = "S08 Art HUD", meta = (BindWidget))
  TObjectPtr<UImage> Icon;

private:
  bool bCodeDefaultTree = false;
};
