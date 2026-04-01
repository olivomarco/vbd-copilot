import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Text,
  Card,
  Button,
  Input,
  ToggleButton,
  TabList,
  Tab,
  Spinner,
  Checkbox,
  Badge,
} from "@fluentui/react-components";
import {
  Search20Regular,
  Grid20Regular,
  List20Regular,
  ArrowDownload20Regular,
  Eye20Regular,
  FolderOpen20Regular,
  CheckboxChecked20Regular,
  DocumentPdf20Regular,
} from "@fluentui/react-icons";
import { useOutputStore } from "@/stores/outputStore";
import { ContentLevelBadge } from "@/components/common/ContentLevelBadge";
import { CategoryIcon } from "@/components/common/AgentIcon";
import type { GroupedOutput, ContentLevel } from "@/api/types";

const CATEGORIES = [
  { value: "all", label: "All" },
  { value: "slides", label: "Slides" },
  { value: "demos", label: "Demos" },
  { value: "hackathons", label: "Hackathons" },
  { value: "ai-projects", label: "AI Projects" },
];

function formatSize(bytes: number): string {
  if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${bytes} B`;
}

function handleZipDownload(files: string[], name: string) {
  fetch("/outputs/zip", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paths: files, name }),
  })
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.blob();
    })
    .then((blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${name}.zip`;
      a.click();
      URL.revokeObjectURL(url);
    })
    .catch((e) => alert(`ZIP download failed: ${e.message}`));
}

export function OutputLibrary() {
  const navigate = useNavigate();
  const {
    loading,
    categoryFilter,
    searchQuery,
    viewMode,
    fetch: fetchOutputs,
    setCategoryFilter,
    setSearchQuery,
    setViewMode,
    filteredGrouped,
  } = useOutputStore();

  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchOutputs();
  }, []);

  const outputs = filteredGrouped();

  const toggleSelect = useCallback((id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const handleBulkZip = useCallback(() => {
    const allFiles: string[] = [];
    for (const o of outputs) {
      if (selected.has(o.id)) {
        allFiles.push(...o.files);
      }
    }
    if (allFiles.length > 0) {
      handleZipDownload(allFiles, "csa-copilot-export");
    }
  }, [selected, outputs]);

  const handlePreview = (o: GroupedOutput) => {
    if (o.category === "slides") {
      navigate(`/library/slides?path=${encodeURIComponent(o.primary_file)}`);
    } else if (o.category === "demos") {
      navigate(`/library/markdown?path=${encodeURIComponent(o.primary_file)}`);
    } else {
      // hackathons and ai-projects → project explorer
      navigate(`/library/project?path=${encodeURIComponent(o.primary_file)}`);
    }
  };

  return (
    <div style={{ padding: "32px 48px", maxWidth: 1400, margin: "0 auto" }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 24,
        }}
      >
        <Text
          as="h1"
          size={700}
          weight="bold"
          style={{ letterSpacing: "-0.03em" }}
        >
          Output Library
        </Text>
        <Input
          contentBefore={<Search20Regular />}
          placeholder="Search outputs..."
          value={searchQuery}
          onChange={(_, d) => setSearchQuery(d.value)}
          style={{ width: 280 }}
        />
      </div>

      {/* Filter bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          marginBottom: 24,
          flexWrap: "wrap",
        }}
      >
        <TabList
          selectedValue={categoryFilter}
          onTabSelect={(_, d) => setCategoryFilter(d.value as string)}
          size="small"
        >
          {CATEGORIES.map((c) => (
            <Tab key={c.value} value={c.value}>
              {c.label}
            </Tab>
          ))}
        </TabList>

        <div style={{ flex: 1 }} />

        <ToggleButton
          appearance={selectMode ? "primary" : "subtle"}
          icon={<CheckboxChecked20Regular />}
          size="small"
          onClick={() => {
            setSelectMode(!selectMode);
            setSelected(new Set());
          }}
          checked={selectMode}
        >
          Select
        </ToggleButton>

        {selectMode && selected.size > 0 && (
          <Button
            appearance="primary"
            icon={<ArrowDownload20Regular />}
            size="small"
            onClick={handleBulkZip}
          >
            ZIP ({selected.size})
          </Button>
        )}

        <div style={{ display: "flex", gap: 4 }}>
          <ToggleButton
            appearance={viewMode === "grid" ? "primary" : "subtle"}
            icon={<Grid20Regular />}
            size="small"
            onClick={() => setViewMode("grid")}
            checked={viewMode === "grid"}
          />
          <ToggleButton
            appearance={viewMode === "list" ? "primary" : "subtle"}
            icon={<List20Regular />}
            size="small"
            onClick={() => setViewMode("list")}
            checked={viewMode === "list"}
          />
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div style={{ display: "flex", justifyContent: "center", padding: 64 }}>
          <Spinner label="Loading outputs..." />
        </div>
      )}

      {/* Empty state */}
      {!loading && outputs.length === 0 && (
        <div
          style={{
            textAlign: "center",
            padding: "80px 0",
            color: "var(--text-secondary)",
          }}
        >
          <Text size={500} style={{ display: "block", marginBottom: 8 }}>
            No outputs found
          </Text>
          <Text size={300}>
            Generate your first content from the Launchpad
          </Text>
        </div>
      )}

      {/* Grid view */}
      {!loading && viewMode === "grid" && outputs.length > 0 && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
            gap: 16,
          }}
        >
          {outputs.map((o, i) => {
            const level = o.content_level as ContentLevel | null;
            return (
              <Card
                key={o.id}
                className="animate-in"
                style={{
                  animationDelay: `${i * 30}ms`,
                  border: selected.has(o.id)
                    ? "2px solid var(--brand-primary)"
                    : "1px solid var(--border)",
                  borderRadius: 12,
                  overflow: "hidden",
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
                onClick={() =>
                  selectMode ? toggleSelect(o.id) : handlePreview(o)
                }
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.transform =
                    "translateY(-2px)";
                  (e.currentTarget as HTMLElement).style.boxShadow =
                    "0 6px 20px rgba(0,0,0,0.07)";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.transform =
                    "translateY(0)";
                  (e.currentTarget as HTMLElement).style.boxShadow = "none";
                }}
              >
                {/* Header area */}
                <div
                  style={{
                    height: 80,
                    background: "linear-gradient(135deg, #0078D410, #00A4EF10)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    position: "relative",
                  }}
                >
                  {selectMode && (
                    <div style={{ position: "absolute", top: 6, left: 6 }}>
                      <Checkbox
                        checked={selected.has(o.id)}
                        onChange={() => toggleSelect(o.id)}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </div>
                  )}
                  <CategoryIcon category={o.category} size="large" />
                  {level && (
                    <div style={{ position: "absolute", top: 8, right: 8 }}>
                      <ContentLevelBadge level={level} size={32} />
                    </div>
                  )}
                </div>

                <div style={{ padding: "16px 18px" }}>
                  <Text
                    weight="semibold"
                    size={400}
                    style={{
                      display: "block",
                      marginBottom: 6,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {o.title}
                  </Text>

                  {/* Metadata badges */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      marginBottom: 10,
                      flexWrap: "wrap",
                    }}
                  >
                    <Badge size="small" appearance="tint" color="informative">
                      {o.category}
                    </Badge>
                    {o.duration && (
                      <Badge size="small" appearance="tint">
                        {o.duration}
                      </Badge>
                    )}
                    {o.has_pdf && (
                      <Badge
                        size="small"
                        appearance="tint"
                        color="success"
                        icon={<DocumentPdf20Regular />}
                      >
                        PDF
                      </Badge>
                    )}
                    <Text
                      size={100}
                      style={{
                        color: "var(--text-secondary)",
                        fontSize: 11,
                      }}
                    >
                      {o.file_count} file{o.file_count !== 1 ? "s" : ""} ·{" "}
                      {formatSize(o.size)}
                    </Text>
                  </div>

                  <Text
                    size={200}
                    style={{ color: "var(--text-secondary)", display: "block" }}
                  >
                    {new Date(o.modified * 1000).toLocaleDateString()}
                  </Text>

                  {/* Actions */}
                  <div
                    style={{
                      display: "flex",
                      gap: 4,
                      marginTop: 12,
                      borderTop: "1px solid var(--border)",
                      paddingTop: 10,
                    }}
                  >
                    <Button
                      appearance="subtle"
                      icon={<Eye20Regular />}
                      size="small"
                      title="Preview"
                      onClick={(e) => {
                        e.stopPropagation();
                        handlePreview(o);
                      }}
                    />
                    <Button
                      appearance="subtle"
                      icon={<ArrowDownload20Regular />}
                      size="small"
                      title={
                        o.file_count > 1 ? "Download as ZIP" : "Download"
                      }
                      onClick={(e) => {
                        e.stopPropagation();
                        if (o.file_count > 1) {
                          handleZipDownload(o.files, o.id.replace("/", "-"));
                        } else {
                          const a = document.createElement("a");
                          a.href = `/file/download?path=${encodeURIComponent(o.primary_file)}`;
                          a.download =
                            o.primary_file.split("/").pop() || "download";
                          a.click();
                        }
                      }}
                    />
                    <Button
                      appearance="subtle"
                      icon={<FolderOpen20Regular />}
                      size="small"
                      title="Open folder"
                      onClick={(e) => {
                        e.stopPropagation();
                        const dir = o.primary_file.substring(
                          0,
                          o.primary_file.lastIndexOf("/"),
                        );
                        if (window.csaStudio) {
                          window.csaStudio.openPath(dir);
                        }
                      }}
                    />
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* List view */}
      {!loading && viewMode === "list" && outputs.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {outputs.map((o, i) => {
            const level = o.content_level as ContentLevel | null;
            return (
              <div
                key={o.id}
                className="animate-in"
                role="button"
                tabIndex={0}
                style={{
                  animationDelay: `${i * 20}ms`,
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  padding: "10px 16px",
                  cursor: "pointer",
                  display: "flex",
                  flexDirection: "row",
                  alignItems: "center",
                  gap: 14,
                  transition: "all 0.1s ease",
                  background: "var(--card-bg)",
                }}
                onClick={() => handlePreview(o)}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.background =
                    "var(--hover-bg)";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.background =
                    "var(--card-bg)";
                }}
              >
                <CategoryIcon category={o.category} size="inline" />
                {level && <ContentLevelBadge level={level} size={26} />}
                <Text weight="semibold" size={300} style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {o.title}
                </Text>
                <Badge size="small" appearance="tint" color="informative">
                  {o.category}
                </Badge>
                {o.duration && (
                  <Text
                    size={200}
                    style={{ color: "var(--text-secondary)", minWidth: 50, flexShrink: 0 }}
                  >
                    {o.duration}
                  </Text>
                )}
                <Text
                  size={200}
                  style={{ color: "var(--text-secondary)", minWidth: 50, flexShrink: 0 }}
                >
                  {o.file_count} file{o.file_count !== 1 ? "s" : ""}
                </Text>
                <Text
                  size={200}
                  style={{ color: "var(--text-secondary)", minWidth: 60, flexShrink: 0 }}
                >
                  {formatSize(o.size)}
                </Text>
                <Text
                  size={200}
                  style={{ color: "var(--text-secondary)", minWidth: 80, flexShrink: 0 }}
                >
                  {new Date(o.modified * 1000).toLocaleDateString()}
                </Text>
                <Button
                  appearance="subtle"
                  icon={<Eye20Regular />}
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    handlePreview(o);
                  }}
                />
                <Button
                  appearance="subtle"
                  icon={<ArrowDownload20Regular />}
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (o.file_count > 1) {
                      handleZipDownload(o.files, o.id.replace("/", "-"));
                    } else {
                      const a = document.createElement("a");
                      a.href = `/file/download?path=${encodeURIComponent(o.primary_file)}`;
                      a.download =
                        o.primary_file.split("/").pop() || "download";
                      a.click();
                    }
                  }}
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
