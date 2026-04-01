import { CONTENT_LEVEL_META, type ContentLevel } from "@/api/types";

interface Props {
  level: ContentLevel;
  size?: number;
}

export function ContentLevelBadge({ level, size = 40 }: Props) {
  const meta = CONTENT_LEVEL_META[level];
  const borderWidth = Math.max(3, size / 10);

  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        border: `${borderWidth}px solid ${meta.color}`,
        background: "#12121A",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
      }}
      title={`${level} — ${meta.meaning}`}
    >
      <span
        style={{
          color: "#fff",
          fontWeight: 700,
          fontSize: size * 0.3,
          lineHeight: 1,
          letterSpacing: "-0.02em",
        }}
      >
        {level}
      </span>
    </div>
  );
}
