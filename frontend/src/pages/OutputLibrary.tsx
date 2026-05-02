import { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useJobStore } from "@/stores/jobStore";
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
  SlideText20Regular,
  Play20Regular,
  Trophy20Regular,
  Rocket20Regular,
  Apps20Regular,
  Add20Regular,
  Delete20Regular,
  Warning20Regular,
} from "@fluentui/react-icons";
import { useOutputStore } from "@/stores/outputStore";
import { ContentLevelBadge } from "@/components/common/ContentLevelBadge";
import { CategoryIcon } from "@/components/common/AgentIcon";
import { deleteGroupedOutput } from "@/api/client";
import type { GroupedOutput, ContentLevel } from "@/api/types";

const CATEGORIES = [
  { value: "all", label: "All", icon: Apps20Regular, color: "#0078D4",
    empty: "Your output library is empty",
    emptyHint: "Head to the Launchpad and generate your first content — slides, demos, hackathons, or full AI projects." },
  { value: "slides", label: "Slides", icon: SlideText20Regular, color: "#0078D4",
    empty: "No slide decks yet",
    emptyHint: "Generate a presentation from the Launchpad — pick a topic, level, and let the slide conductor handle the rest." },
  { value: "demos", label: "Demos", icon: Play20Regular, color: "#7FBA00",
    empty: "No demo guides yet",
    emptyHint: "Create a step-by-step demo guide from the Launchpad — complete with scripts, talking points, and timing." },
  { value: "hackathons", label: "Hackathons", icon: Trophy20Regular, color: "#FFB900",
    empty: "No hackathon packages yet",
    emptyHint: "Build a full hackathon-in-a-box from the Launchpad — challenges, coaching guides, scoring rubrics, and starter code." },
  { value: "ai-projects", label: "AI Projects", icon: Rocket20Regular, color: "#F25022",
    empty: "No AI projects yet",
    emptyHint: "Kick off an AI project from the Launchpad — architecture docs, infrastructure code, source, tests, and CI/CD in one go." },
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
    fetchForce,
    setCategoryFilter,
    setSearchQuery,
    setViewMode,
    filteredGrouped,
  } = useOutputStore();

  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [deleteTarget, setDeleteTarget] = useState<GroupedOutput | null>(null);
  const [deleting, setDeleting] = useState(false);
  const deleteBannerRef = useRef<HTMLDivElement>(null);

  const handleDelete = useCallback(async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteGroupedOutput(deleteTarget.id);
      setDeleteTarget(null);
      await fetchOutputs();
    } catch (e: any) {
      alert(`Delete failed: ${e.message}`);
    } finally {
      setDeleting(false);
    }
  }, [deleteTarget, fetchOutputs]);

  useEffect(() => {
    fetchOutputs();
  }, []);

  // Re-fetch whenever any job delivers new output files (triggered by the
  // server's "new_files" WebSocket event landing in the job store).
  const totalOutputFiles = useJobStore(
    (s) => Object.values(s.jobs).reduce((n, j) => n + j.outputFiles.length, 0),
  );
  const prevOutputFilesRef = useRef(totalOutputFiles);
  useEffect(() => {
    if (totalOutputFiles > prevOutputFilesRef.current) {
      fetchForce();  // bypass TTL — new files just arrived
    }
    prevOutputFilesRef.current = totalOutputFiles;
  }, [totalOutputFiles, fetchForce]);

  useEffect(() => {
    if (deleteTarget && deleteBannerRef.current) {
      deleteBannerRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [deleteTarget]);

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
    } else if (o.category === "demos" && o.file_count === 1) {
      navigate(`/library/markdown?path=${encodeURIComponent(o.primary_file)}`);
    } else {
      // demos with multiple files, hackathons, and ai-projects → project explorer
      navigate(`/library/project?path=${encodeURIComponent(o.primary_file)}&id=${encodeURIComponent(o.id)}`);
    }
  };

  return (
    <div className="page-container" style={{ padding: "32px 48px", maxWidth: 1400, margin: "0 auto" }}>
      {/* Header */}
      <div
        className="header-row"
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
          className="search-input"
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
            <Tab key={c.value} value={c.value} icon={<c.icon />}>
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

      {/* Delete confirmation banner */}
      {deleteTarget && (
        <div
          ref={deleteBannerRef}
          className="animate-in"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 14,
            padding: "14px 20px",
            marginBottom: 20,
            background: "var(--bg-hint)",
            border: "1px solid #FFB90060",
            borderLeft: "4px solid #F25022",
            borderRadius: 10,
          }}
        >
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: "50%",
              background: "#F2502218",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <Warning20Regular style={{ color: "#F25022" }} />
          </div>
          <div style={{ flex: 1 }}>
            <Text weight="semibold" size={300} style={{ display: "block", color: "var(--text-warning)" }}>
              Delete "{deleteTarget.title}"?
            </Text>
            <Text size={200} style={{ color: "var(--text-warning)" }}>
              This will permanently remove {deleteTarget.file_count} file{deleteTarget.file_count !== 1 ? "s" : ""} ({formatSize(deleteTarget.size)}). This action cannot be undone.
            </Text>
          </div>
          <Button
            appearance="subtle"
            size="small"
            onClick={() => setDeleteTarget(null)}
            disabled={deleting}
          >
            Cancel
          </Button>
          <Button
            appearance="primary"
            size="small"
            icon={<Delete20Regular />}
            onClick={handleDelete}
            disabled={deleting}
            style={{ background: "#F25022", borderColor: "#F25022" }}
          >
            {deleting ? "Deleting…" : "Delete"}
          </Button>
        </div>
      )}
      {/* Loading */}
      {loading && (
        <div style={{ display: "flex", justifyContent: "center", padding: 64 }}>
          <Spinner label="Loading outputs..." />
        </div>
      )}

      {/* Empty state */}
      {!loading && outputs.length === 0 && (() => {
        const cat = CATEGORIES.find((c) => c.value === categoryFilter) || CATEGORIES[0];
        const IconComp = cat.icon;
        return (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              padding: "80px 24px",
              gap: 16,
            }}
          >
            <div
              style={{
                width: 80,
                height: 80,
                borderRadius: 24,
                background: `${cat.color}10`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: 8,
              }}
            >
              <IconComp style={{ width: 36, height: 36, color: cat.color, opacity: 0.7 }} />
            </div>
            <Text size={500} weight="semibold" style={{ color: "var(--text-primary)" }}>
              {cat.empty}
            </Text>
            <Text
              size={300}
              style={{
                color: "var(--text-secondary)",
                maxWidth: 420,
                textAlign: "center",
                lineHeight: 1.5,
              }}
            >
              {cat.emptyHint}
            </Text>
            <Button
              appearance="primary"
              icon={<Add20Regular />}
              style={{ marginTop: 8 }}
              onClick={() => navigate("/")}
            >
              Go to Launchpad
            </Button>
          </div>
        );
      })()}

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
                        if (window.csaStudio) {
                          const dir = o.primary_file.substring(
                            0,
                            o.primary_file.lastIndexOf("/"),
                          );
                          window.csaStudio.openPath(dir);
                        } else {
                          navigate(
                            `/library/project?path=${encodeURIComponent(o.primary_file)}&id=${encodeURIComponent(o.id)}`,
                          );
                        }
                      }}
                    />
                    <div style={{ flex: 1 }} />
                    <Button
                      appearance="subtle"
                      icon={<Delete20Regular />}
                      size="small"
                      title="Delete"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteTarget(o);
                      }}
                      style={{ color: "var(--text-secondary)" }}
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
                <div style={{ display: "flex", alignItems: "center", gap: 8, width: 68, flexShrink: 0, justifyContent: "flex-start" }}>
                  <CategoryIcon category={o.category} size="inline" />
                  {level ? <ContentLevelBadge level={level} size={26} /> : <div style={{ width: 26 }} />}
                </div>
                <Text weight="semibold" size={300} style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {o.title}
                </Text>
                <Badge size="small" appearance="tint" color="informative" style={{ minWidth: 80, textAlign: "center" }}>
                  {o.category}
                </Badge>
                <Text
                  size={200}
                  style={{ color: "var(--text-secondary)", width: 50, flexShrink: 0, textAlign: "right" }}
                >
                  {o.duration || ""}
                </Text>
                <Text
                  size={200}
                  style={{ color: "var(--text-secondary)", width: 50, flexShrink: 0, textAlign: "right" }}
                >
                  {o.file_count} file{o.file_count !== 1 ? "s" : ""}
                </Text>
                <Text
                  size={200}
                  style={{ color: "var(--text-secondary)", width: 60, flexShrink: 0, textAlign: "right" }}
                >
                  {formatSize(o.size)}
                </Text>
                <Text
                  size={200}
                  style={{ color: "var(--text-secondary)", width: 80, flexShrink: 0, textAlign: "right" }}
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
                <Button
                  appearance="subtle"
                  icon={<Delete20Regular />}
                  size="small"
                  title="Delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeleteTarget(o);
                  }}
                  style={{ color: "var(--text-secondary)" }}
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
