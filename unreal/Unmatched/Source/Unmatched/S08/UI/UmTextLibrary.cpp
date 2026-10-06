#include "UmTextLibrary.h"

#include "Internationalization/StringTable.h"
#include "Internationalization/StringTableCore.h"

bool UUmTextLibrary::AuthorStringTable(UStringTable* Table, const FString& Namespace, const FString& Csv) {
  if (!Table) return false;
  Table->Modify();
  const FStringTableRef Strings = Table->GetMutableStringTable();
  Strings->SetNamespace(Namespace);  // before the import: the entries take the table namespace
  const bool bOk = Strings->ImportStringsFromCSVString(Csv, *Table->GetPathName());
  Table->MarkPackageDirty();
  return bOk;
}
