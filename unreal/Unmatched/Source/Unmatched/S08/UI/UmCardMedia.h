// VS-1 CP-02 (docs/game-design/visual/06-tasks/cards-portraits.csv CP-02; 02-visual-design.md §6.1, §6.4, §12;
// 08-integration-decisions.md INT-014, INT-016, INT-018): the key registry of the real card scans, card backs and
// portraits the client finds by content key - never by cuid, never by URL at runtime (INT-015).
//
//   Config/Cards/S08CardMedia.json   written by tools/art/cards/ue_import_card_media.py (in git, no pixels), staged into
//                                    the pak (Unmatched.Build.cs RuntimeDependencies). Per entry: key, lang (cards),
//                                    object path, src (source size), pad (power-of-two size), uv = src / pad (the
//                                    source sits in the top-left of the padded texture, padding #061623 alpha 0),
//                                    sha256 of the PNG, disc [cx, cy, d] for portraits (fractions of the source side:
//                                    ВР-CP01 starting numbers until CP-07 is reviewed).
//   keys      cards      heroSlug:cardSlug + lang ru|en (ВР-51: RU build = RU scans 287x398, EN = EN scans 250x349)
//             backs      back:<heroSlug>
//             portraits  portrait:<heroSlug> and portrait:<heroSlug>:<sidekickSlug>
//   assets    /Game/S08/UI/Cards/<hero>/T_Card_<hero>_<card>_<RU|EN>, /Game/S08/UI/CardBacks/T_CardBack_<hero>,
//             /Game/S08/UI/Portraits/T_Portrait_<hero>[_<sidekick>] ('-' -> '_', ВР-CP07); gitignored Content
//             (GAP-019 / ENV-U3: the scans are third-party art) - another checkout runs the import script.
//
// The rollback flags -S08PortraitLegacy / -S08CardArtLegacy live in S08ArtLook.h (ВР-CP08, traced in ARTLOOK).
// -ArtPreviewCardMediaProbe (review tooling): the board actor loads every registry texture once and writes
//   CARDMEDIA probe entries=<n> loaded=<n> missing=<n> [first=<object path>]
// so a packaged run proves the textures are cooked (no "Failed to load" by registry paths).
#pragma once

#include "CoreMinimal.h"

class UTexture2D;

struct UNMATCHED_API FUmCardMediaEntry {
  FString Key;         // heroSlug:cardSlug | back:<hero> | portrait:<hero>[:<sidekick>]
  FString Kind;        // card | back | portrait
  FString Lang;        // ru | en for cards, empty otherwise
  FString ObjectPath;  // /Game/S08/UI/...Package.AssetName
  FIntPoint Src = FIntPoint::ZeroValue;
  FIntPoint Pad = FIntPoint::ZeroValue;
  FVector2D Uv = FVector2D::ZeroVector;  // src / pad: the UV rectangle (0,0)-(Uv) of the source pixels
  FString Sha256;
  bool bHasDisc = false;
  FVector Disc = FVector::ZeroVector;  // portraits: centre x, centre y, diameter in fractions of the source side
};

namespace UmCardMedia {

inline const TCHAR* const ConfigSubdir = TEXT("Cards");
inline const TCHAR* const FileName = TEXT("S08CardMedia.json");
inline const TCHAR* const Schema = TEXT("unmatched.s08-card-media/1");
/** Review tooling: load every registry texture once on the board actor's BeginPlay and trace the result. */
inline const TCHAR* const ProbeFlagName = TEXT("ArtPreviewCardMediaProbe");

/** <Project>/Config/Cards/S08CardMedia.json. */
UNMATCHED_API FString RegistryPath();
/** Parses a registry document; false (with Errors) on a broken schema - an invalid entry is never half-loaded. */
UNMATCHED_API bool Parse(const FString& Json, TArray<FUmCardMediaEntry>& Out, TArray<FString>& Errors);
/** The shipped registry, read once (an unreadable file logs a Warning and yields an empty registry: INT-018 fallback). */
UNMATCHED_API const TArray<FUmCardMediaEntry>& Registry();
/** Automation tests: drop the cached registry (the next Registry() reads the file again). */
UNMATCHED_API void ResetForTest();

UNMATCHED_API const FUmCardMediaEntry* FindCard(const FString& HeroSlug, const FString& CardSlug, const FString& Lang);
UNMATCHED_API const FUmCardMediaEntry* FindBack(const FString& HeroSlug);
UNMATCHED_API const FUmCardMediaEntry* FindPortrait(const FString& HeroSlug, const FString& SidekickSlug = FString());
/** 'ru' unless the current culture is English (the RU build is the default, ВР-51 / HB-05). */
UNMATCHED_API FString PreferredLang();
/** Synchronous load of the entry's texture; nullptr (and a Warning naming the key) when it is not imported / cooked. */
UNMATCHED_API UTexture2D* LoadTexture(const FUmCardMediaEntry& Entry);

/** The asset name rule of ue_import_card_media.py ('-' -> '_'): T_Card_<hero>_<card>_<RU|EN> and so on. */
UNMATCHED_API FString CardAssetName(const FString& HeroSlug, const FString& CardSlug, const FString& Lang);

/** True with -ArtPreviewCardMediaProbe on this command line. */
UNMATCHED_API bool ProbeRequested(const TCHAR* CommandLine);
/** Loads every registry texture: "CARDMEDIA probe entries=<n> loaded=<n> missing=<n>[ first=<path>]". */
UNMATCHED_API FString ProbeLine();

}  // namespace UmCardMedia
