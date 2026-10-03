// Art Tuner M2 (docs/art-pipeline/ART-TUNER-PLAN.md §3-5, §8): the data model of the in-game tuning panel.
//
// The panel edits the board profiles document (Config/ArtBoards/S08ArtBoardProfiles.json) through RFC 6901 JSON pointers
// listed in a registry (Config/ArtTuner/S08ArtTunerParams.json: label, range, step, scope per row). The model keeps the
// document text it started from (the base) and the changed values (entries); every change rebuilds the document text
// and runs it through FS08BoardArtData::ParseJson - the SAME parser and validation as the game start - so what the scene
// shows is always a valid document, and the saved file is exactly that document minus the base. "Save" writes only the
// entries to S08ArtTuner.overrides.json (-ArtTunerFile=<abs>); a start with that file puts them back; the fold tool
// (tools/art/art_tuner_fold.py) writes them into the profile text. Nothing of this runs without -ArtTuner.
#pragma once

#include "CoreMinimal.h"
#include "S08BoardArt.h"

class FJsonObject;
class FJsonValue;
class SS08ArtTunerPanel;

namespace S08ArtTunerSpec {
inline const TCHAR* const FlagName = TEXT("ArtTuner");
inline const TCHAR* const FileParam = TEXT("ArtTunerFile=");
inline const TCHAR* const ParamsSchema = TEXT("unmatched.art-tuner-params/1");
inline const TCHAR* const OverridesSchema = TEXT("unmatched.art-tuner-overrides/1");
/** Direct (component) applies at most this often while a slider moves; a rebuild-scope change at most RebuildHz. */
constexpr float ApplyHz = 30.0f;
constexpr float RebuildHz = 4.0f;
/** <ProjectConfigDir>/ArtTuner/S08ArtTunerParams.json (staged as UFS, Unmatched.Build.cs). */
UNMATCHED_API FString DefaultParamsPath();
/** -ArtTuner on the command line. */
UNMATCHED_API bool Enabled(const TCHAR* CommandLine = nullptr);
/** -ArtTunerFile=<abs> (empty = saving is off; the panel says so). */
UNMATCHED_API FString FileFromCommandLine(const TCHAR* CommandLine = nullptr);
}  // namespace S08ArtTunerSpec

/** How a change reaches the scene (registry "scope"); a set of them is applied per tick. */
enum class ES08TunerScope : uint8 {
  None = 0,
  HeroLight = 1 << 0,      // AS08BoardActor::UpdateHeroLights (the rigs are reused)
  ProfileLights = 1 << 1,  // the light profile's actors: key, points, sky, fog, exposure volume
  MapGrade = 1 << 2,       // the map plane MID
  ConceptLights = 1 << 3,  // the lit3d point lights (+ their flicker base)
  Materials = 1 << 4,      // the lit3d material overrides (MIDs)
  Rebuild = 1 << 5,        // a full board rebuild (throttled)
};
ENUM_CLASS_FLAGS(ES08TunerScope);
UNMATCHED_API bool S08TunerScopeFromName(const FString& Name, ES08TunerScope& Out);
UNMATCHED_API FString S08TunerScopeNames(ES08TunerScope Scopes);

enum class ES08TunerType : uint8 { Number, Bool, ColorSrgb, ColorLinear, Ev100 };
UNMATCHED_API const TCHAR* S08TunerTypeName(ES08TunerType Type);

namespace S08JsonPointer {
/** RFC 6901: "" = the root, "/a/b~1c/0" -> a, b/c, 0. False for a non-empty pointer without the leading '/'. */
UNMATCHED_API bool Split(const FString& Pointer, TArray<FString>& OutSegments);
UNMATCHED_API FString Escape(const FString& Segment);
/** The value at Pointer (null when a segment is missing or an array index is out of range / not a number). */
UNMATCHED_API TSharedPtr<FJsonValue> Get(const TSharedPtr<FJsonObject>& Root, const FString& Pointer);
/** Replaces the value at Pointer in place. bCreateLeaf: the last segment may be a new key of an existing object. Arrays
 *  are rebuilt (FJsonValueArray holds its elements by value). */
UNMATCHED_API bool Set(const TSharedPtr<FJsonObject>& Root, const FString& Pointer, const TSharedPtr<FJsonValue>& Value,
                       bool bCreateLeaf, FString& OutError);
/** Compact JSON text of one value (numbers as the shortest round-trip text of a NumberString). */
UNMATCHED_API FString ToText(const TSharedPtr<FJsonValue>& Value);
/** Same type and value (numbers within 1e-9, arrays element-wise). */
UNMATCHED_API bool Equal(const TSharedPtr<FJsonValue>& A, const TSharedPtr<FJsonValue>& B);
}  // namespace S08JsonPointer

/** One concrete panel row (registry template resolved for a board). */
struct UNMATCHED_API FS08TunerParam {
  FString Id;       // <group>.<param>[#<index>]
  FString GroupId;
  FString Label;
  FString Unit;
  FString Note;
  FString Pointer;  // resolved (Ev100: the exposure block)
  ES08TunerType Type = ES08TunerType::Number;
  ES08TunerScope Scope = ES08TunerScope::None;
  bool bHasMin = false;
  bool bHasMax = false;
  bool bMinHard = false;
  bool bMaxHard = false;
  double Min = 0.0;
  double Max = 0.0;
  double SliderMin = 0.0;
  double SliderMax = 1.0;
  double Step = 0.01;
  bool bCross = false;   // the parser checks it together with other fields (cone pair, heights, fog range)
  bool bCreate = false;  // the key may be absent (the row writes a new optional field)
  /** Decimals of Step (0.05 -> 2, 1 -> 0): the saved text of a value. */
  int32 Decimals() const;
  /** Value snapped to Step and clamped to the hard bounds. */
  double Snap(double Value) const;
};

struct UNMATCHED_API FS08TunerGroup {
  FString Id;
  FString Label;
  FString Note;          // e.g. hidden by the board's lit3d.hide
  bool bInert = false;   // the note says the rows do not change the scene on this board
  ES08TunerScope Scope = ES08TunerScope::None;
  TArray<FS08TunerParam> Params;
};

/** Config/ArtTuner/S08ArtTunerParams.json: group / row templates. */
class UNMATCHED_API FS08ArtTunerRegistry {
public:
  bool Parse(const FString& Text, TArray<FString>& OutErrors);
  bool LoadFile(const FString& Path, TArray<FString>& OutErrors);
  /** The rows for one board of Doc: {profile} / {board} resolved, "each" groups expanded per array element, rows whose
   *  pointer is absent dropped (unless "create" and the parent object exists), empty groups dropped. */
  TArray<FS08TunerGroup> Expand(const TSharedPtr<FJsonObject>& Doc, const FString& ProfileId, int32 BoardIndex) const;
  int32 NumTemplates() const;

private:
  struct FTemplateGroup {
    FString Id, Label, When, Each, HiddenIfPointer, HiddenIfContains, HiddenNote;
    ES08TunerScope Scope = ES08TunerScope::None;
    TArray<FS08TunerParam> Params;  // Pointer / Label are templates
  };
  TArray<FTemplateGroup> Groups;
};

/** One changed value. */
struct UNMATCHED_API FS08TunerEntry {
  FString Pointer;
  TSharedPtr<FJsonValue> Value;
};

/** Base document + entries -> a parsed FS08BoardArtData. */
class UNMATCHED_API FS08ArtTunerModel {
public:
  bool SetBase(const FString& Text, const FString& Sha256, TArray<FString>& OutErrors);
  bool HasBase() const { return Base.IsValid(); }
  const TSharedPtr<FJsonObject>& GetBase() const { return Base; }
  const FString& GetBaseSha256() const { return BaseSha256; }
  int32 GetBaseRevision() const;
  /** The base value at Pointer (null when absent). */
  TSharedPtr<FJsonValue> BaseValue(const FString& Pointer) const;
  /** The entry value, else the base value. */
  TSharedPtr<FJsonValue> Value(const FString& Pointer) const;
  bool IsChanged(const FString& Pointer) const { return IndexOf(Pointer) != INDEX_NONE; }
  /** Stores a value (a value equal to the base removes the entry). Refused: a pointer that is neither in the base nor an
   *  allowed new key (bCreate + an existing parent object), or a value of another JSON type than the base one. */
  bool SetValue(const FString& Pointer, const TSharedPtr<FJsonValue>& Value, bool bCreate, FString& OutError);
  void Reset(const FString& Pointer);
  void ResetAll() { Entries.Reset(); }
  const TArray<FS08TunerEntry>& GetEntries() const { return Entries; }
  /** The base text with every entry written in (compact JSON). */
  bool BuildText(FString& OutText, TArray<FString>& OutErrors) const;
  /** BuildText -> FS08BoardArtData::ParseJson (SourceSha256 = the base file's). */
  bool Build(FS08BoardArtData& OutData, TArray<FString>& OutErrors) const;

private:
  int32 IndexOf(const FString& Pointer) const;
  FString BaseText;
  FString BaseSha256;
  TSharedPtr<FJsonObject> Base;
  TArray<FS08TunerEntry> Entries;
};

/** S08ArtTuner.overrides.json: {schema, savedAt, baseProfilesSha256, baseRevision, boards: [{board, profile, anchors,
 *  entries: [{pointer, value, was}]}]} - one block per board, so saving one map keeps the others. */
struct UNMATCHED_API FS08TunerOverridesFile {
  struct FEntry {
    FString Pointer;
    TSharedPtr<FJsonValue> Value;
    TSharedPtr<FJsonValue> Was;  // the base value at save time (null = the key was new)
  };
  struct FBoard {
    FString Board;    // board profile id (boards[].id)
    FString Profile;  // light profile id
    TArray<TPair<FString, FString>> Anchors;  // pointer -> expected string (e.g. /boards/4/id -> sarpedon-original)
    TArray<FEntry> Entries;
  };
  FString SavedAt;
  FString BaseSha256;
  int32 BaseRevision = 0;
  TArray<FBoard> Boards;

  bool Parse(const FString& Text, TArray<FString>& OutErrors);
  bool LoadFile(const FString& Path, TArray<FString>& OutErrors);
  FString ToJson() const;
  FBoard* FindBoard(const FString& Board);
  /** Replaces (or adds) the block of one board. */
  void PutBoard(const FBoard& Board);
};

namespace S08ArtTuner {
/** The saved text of a number: Decimals places, trailing zeros cut ("7.50" -> "7.5", "-0" -> "0"). */
UNMATCHED_API FString FormatNumber(double Value, int32 Decimals);
/** "#rgb..." -> "#RRGGBB" (upper case); false when not 6 hex digits. */
UNMATCHED_API bool NormalizeHex(const FString& In, FString& Out);
/** Validates and snaps one panel value into the (pointer, value) writes of its row: a number snapped to the step with the
 *  hard bounds checked, a bool, a #RRGGBB, three linear channels, or ev100 (ev100 + min = max brightness 2^ev). */
UNMATCHED_API bool ValueWrites(const FS08TunerParam& Param, const TSharedPtr<FJsonValue>& Value,
                               TArray<TPair<FString, TSharedPtr<FJsonValue>>>& OutWrites, FString& OutError);
}  // namespace S08ArtTuner

/** One -ArtTuner session of the game mode (S08FlowGameModeArtTuner.cpp): the registry rows of the active board, the
 *  model, the pending apply and the panel. Null without the flag. */
struct FS08ArtTunerSession {
  FS08ArtTunerRegistry Registry;
  FS08ArtTunerModel Model;
  TArray<FS08TunerGroup> Groups;
  FString File;            // -ArtTunerFile (empty: saving off)
  FString ProfilesPath;    // the document the board loaded (pak, -ArtBoardProfiles, or a live-tune reload)
  FString ProfilesSource;  // its RENDER source (pak | override) while nothing is changed
  FString BoardId;         // boards[].id of the active board
  FString LightId;         // its light profile id
  int32 BoardIndex = INDEX_NONE;
  /** The pending document (the model's latest valid build) and the scopes to push; applied at most ApplyHz /
   *  RebuildHz (the slider drag), at once for the live-tune "tune" action. */
  bool bPending = false;
  uint8 PendingScopes = 0;
  FS08BoardArtData PendingData;
  double NextApplyAt = 0.0;
  double NextRebuildAt = 0.0;
  int32 Applies = 0;
  int32 Rebuilds = 0;
  double LastApplyMs = 0.0;
  FString LastApplyNote;
  /** Bumped on every value change (the panel re-reads its rows). */
  int32 Version = 0;
  TArray<FString> Warnings;  // load / file problems (panel status, state)
  FString LastError;
  FString LastSavedAt;
  TSharedPtr<SS08ArtTunerPanel> Panel;
  TSharedPtr<class SWidget> PanelRoot;
  bool bPanelOpen = false;

  const FS08TunerParam* FindParam(const FString& PointerOrId) const;
  const FS08TunerGroup* FindGroup(const FString& Id) const;
};
