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
  float HpFraction = 1.0f;
};

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
