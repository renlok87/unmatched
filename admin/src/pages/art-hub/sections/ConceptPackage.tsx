import React from "react";
import { Alert, Card, Empty, Image, Space, Tag, Typography } from "antd";
import type {
  AcceptanceCardView,
  ConceptChecksView,
  ConceptPackageView,
} from "../../../../art-hub/types";
import { fileUrl } from "../api";
import { FileActions } from "../components/common";

const { Text } = Typography;

const VERDICT_COLOR: Record<string, string> = {
  PASS: "green",
  WARN: "gold",
  FAIL: "red",
  pass: "green",
  rework_blender: "orange",
  escalate_user: "red",
};

export const ChecksTag: React.FC<{
  c?:
    | Pick<ConceptChecksView, "verdict" | "pass" | "warn" | "fail">
    | { verdict?: string; pass?: number; warn?: number; fail?: number };
}> = ({ c }) => {
  if (!c || (c.verdict === undefined && c.pass === undefined)) return null;
  return (
    <Tag
      color={VERDICT_COLOR[c.verdict ?? ""] ?? "default"}
      style={{ marginInlineEnd: 0 }}
    >
      {c.verdict ?? "—"} · FAIL {c.fail ?? 0} / WARN {c.warn ?? 0}
    </Tag>
  );
};

/** Acceptance cards: concept (1a/1c), model (stage 4), anim (stage 6)… */
export const AcceptanceCards: React.FC<{ cards: AcceptanceCardView[] }> = ({
  cards,
}) => {
  if (!cards.length) return null;
  return (
    <div data-testid="art-hub-acceptance-cards">
      <Text strong>Карточки приёмки ({cards.length})</Text>
      <div
        style={{
          marginTop: 6,
          display: "flex",
          flexDirection: "column",
          gap: 6,
        }}
      >
        {cards.map((c) => (
          <Space key={c.file.path} wrap size={6} align="start">
            <Tag>{c.group.replace(/^acceptance-?/, "") || "model"}</Tag>
            <Text code>{c.folder}</Text>
            <Tag
              color={VERDICT_COLOR[c.verdict ?? ""] ?? "default"}
              style={{ marginInlineEnd: 0 }}
            >
              {c.verdict ?? "нет вердикта"}
            </Tag>
            {c.score !== undefined ? (
              <Text>коэффициент {c.score.toFixed(1)}</Text>
            ) : null}
            {c.scores.length ? (
              <Text type="secondary" style={{ fontSize: 12 }}>
                {c.scores.map((s) => `${s.dim} ${s.value ?? "—"}`).join(" · ")}
              </Text>
            ) : null}
            {c.failedGates.length ? (
              <Tag color="red">гейт FAIL: {c.failedGates.join(", ")}</Tag>
            ) : null}
            <FileActions file={c.file} />
          </Space>
        ))}
      </div>
    </div>
  );
};

const STAGE_LABEL: Record<string, string> = {
  старт: "этап 1a: концепт в работе",
  "1a": "этап 1a: дизайн есть",
  "1a-приёмка": "этап 1a: дизайн принят карточкой",
  "1c": "этап 1c: виды и лист",
  "1c-приёмка": "этап 1c: лист принят карточкой",
};

/** Stage-1 package of a new figure: design front, all candidate generations, checks, verification, README status. */
export const ConceptPackage: React.FC<{ pkg: ConceptPackageView }> = ({
  pkg,
}) => {
  const v = pkg.verification;
  const hasThumbs =
    pkg.candidates.some((c) => c.file.servable) || pkg.designFront?.servable;
  return (
    <div data-testid={`art-hub-concept-package-${pkg.contentKey ?? ""}`}>
      <Space wrap size={6} style={{ marginBottom: 6 }}>
        <Text strong>Концепт-пакет 3d-model-pipeline</Text>
        <Tag color="blue">{STAGE_LABEL[pkg.stage] ?? pkg.stage}</Tag>
        <Text code style={{ fontSize: 11 }}>
          {pkg.dir}
        </Text>
        {pkg.readme ? <FileActions file={pkg.readme} /> : null}
        {pkg.prompts ? <FileActions file={pkg.prompts} /> : null}
        <Text type="secondary" style={{ fontSize: 12 }}>
          генераций в записях: {pkg.generationRecords}
        </Text>
      </Space>
      {pkg.readmeStatus ? (
        <div>
          <Text type="secondary" style={{ fontSize: 12 }}>
            README: {pkg.readmeStatus}
          </Text>
        </div>
      ) : null}
      {pkg.palette?.length ? (
        <div style={{ margin: "4px 0" }}>
          {pkg.palette.map((c) => (
            <Tag
              key={c.hex + c.name}
              color={c.hex}
              style={{ color: "#fff", textShadow: "0 0 2px #000" }}
            >
              {c.name || c.hex}
            </Tag>
          ))}
        </div>
      ) : null}
      {v?.limitReached.length ? (
        <Alert
          type="warning"
          showIcon
          style={{ margin: "6px 0" }}
          message={`Лимит генераций исчерпан: ${v.limitReached.map((l) => `${l.view}${l.failedItems.length ? ` (${l.failedItems.join(", ")})` : ""}`).join("; ")}`}
        />
      ) : null}
      {v && !v.limitReached.length && !v.error ? (
        <Text type="secondary" style={{ fontSize: 12 }}>
          verification: лимит не исчерпан
          {v.sourceUnchanged === false ? " · источник изменён!" : ""}
          {v.outsideFolder.length
            ? ` · вне папки: ${v.outsideFolder.length}`
            : ""}
          {v.checklistFailed
            ? ` · провалено пунктов чек-листа: ${v.checklistFailed}`
            : ""}
        </Text>
      ) : null}
      {pkg.warnings.map((w) => (
        <div key={w}>
          <Text type="warning" style={{ fontSize: 12 }}>
            ⚠ {w}
          </Text>
        </div>
      ))}
      {hasThumbs ? (
        <Image.PreviewGroup>
          <div
            style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 8 }}
          >
            {pkg.designFront?.servable ? (
              <Card
                size="small"
                style={{ width: 190 }}
                styles={{ body: { padding: 6 } }}
                title={<Text style={{ fontSize: 12 }}>Выбранный дизайн</Text>}
              >
                <Image
                  src={fileUrl(pkg.designFront)}
                  width={176}
                  height={235}
                  style={{ objectFit: "contain", background: "#f5f5f5" }}
                  alt="design front"
                />
                <ChecksTag c={pkg.designChecks} />
              </Card>
            ) : null}
            {pkg.candidates.map((c) => (
              <Card
                key={c.file.path}
                size="small"
                style={{
                  width: 190,
                  borderColor: c.selected ? "#52c41a" : undefined,
                }}
                styles={{ body: { padding: 6 } }}
                title={
                  <Text style={{ fontSize: 12 }}>
                    {c.label}
                    {c.selected ? " ✓" : ""}
                  </Text>
                }
              >
                {c.file.servable ? (
                  <Image
                    src={fileUrl(c.file)}
                    width={176}
                    height={235}
                    style={{ objectFit: "contain", background: "#f5f5f5" }}
                    alt={c.label}
                  />
                ) : null}
                <ChecksTag c={c} />
              </Card>
            ))}
          </div>
        </Image.PreviewGroup>
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="картинок пока нет (Codex ещё генерирует)"
        />
      )}
      {pkg.views.length || pkg.sheet ? (
        <Image.PreviewGroup>
          <div
            style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 8 }}
          >
            {pkg.views.map((f) => (
              <Card
                key={f.path}
                size="small"
                style={{ width: 190 }}
                styles={{ body: { padding: 6 } }}
                title={<Text style={{ fontSize: 12 }}>{f.role}</Text>}
              >
                {f.servable ? (
                  <Image
                    src={fileUrl(f)}
                    width={176}
                    height={235}
                    style={{ objectFit: "contain", background: "#f5f5f5" }}
                    alt={f.path}
                  />
                ) : null}
              </Card>
            ))}
            {pkg.sheet?.servable ? (
              <Card
                size="small"
                style={{ width: 420 }}
                styles={{ body: { padding: 6 } }}
                title={<Text style={{ fontSize: 12 }}>Лист 1c</Text>}
              >
                <Image
                  src={fileUrl(pkg.sheet)}
                  width={406}
                  style={{ background: "#f5f5f5" }}
                  alt="sheet"
                />
                <ChecksTag c={pkg.sheetChecks} />
              </Card>
            ) : null}
          </div>
        </Image.PreviewGroup>
      ) : null}
    </div>
  );
};
