import { useEffect, useState, useMemo } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  Text,
  Button,
  Spinner,
  Tree,
  TreeItem,
  TreeItemLayout,
} from "@fluentui/react-components";
import {
  ArrowLeft20Regular,
  ArrowDownload20Regular,
  Document20Regular,
  Folder20Regular,
  FolderOpen20Regular,
  Delete20Regular,
} from "@fluentui/react-icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { readFile, listOutputs, listGroupedOutputs } from "@/api/client";
import type { OutputFile } from "@/api/types";
import { DrawioRenderer } from "./DrawioRenderer";

interface TreeNode {
  name: string;
  path?: string;  // full path for files
  type?: string;
  children?: TreeNode[];
}

function buildTree(files: OutputFile[], rootDir: string): TreeNode[] {
  const root: TreeNode = { name: "root", children: [] };

  for (const f of files) {
    // Get path relative to rootDir
    const relIdx = f.path.indexOf(rootDir);
    if (relIdx === -1) continue;
    const rel = f.path.slice(relIdx + rootDir.length).replace(/^\//, "");
    const parts = rel.split("/");

    let current = root;
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      if (i === parts.length - 1) {
        // file
        current.children = current.children || [];
        current.children.push({ name: part, path: f.path, type: f.type });
      } else {
        // directory
        current.children = current.children || [];
        let existing = current.children.find(
          (c) => c.name === part && c.children !== undefined,
        );
        if (!existing) {
          existing = { name: part, children: [] };
          current.children.push(existing);
        }
        current = existing;
      }
    }
  }

  // Sort: folders first, then files
  function sortTree(nodes: TreeNode[]) {
    nodes.sort((a, b) => {
      const aDir = a.children !== undefined ? 0 : 1;
      const bDir = b.children !== undefined ? 0 : 1;
      if (aDir !== bDir) return aDir - bDir;
      return a.name.localeCompare(b.name);
    });
    for (const n of nodes) {
      if (n.children) sortTree(n.children);
    }
  }
  if (root.children) sortTree(root.children);

  return root.children || [];
}

function getLanguage(name: string): string {
  const ext = name.split(".").pop()?.toLowerCase() || "";
  const map: Record<string, string> = {
    py: "python",
    js: "javascript",
    ts: "typescript",
    sh: "bash",
    bicep: "bicep",
    json: "json",
    yaml: "yaml",
    yml: "yaml",
    md: "markdown",
    html: "html",
    css: "css",
  };
  return map[ext] || "text";
}

function FileTreeItem({
  node,
  onSelect,
  selectedPath,
}: {
  node: TreeNode;
  onSelect: (path: string) => void;
  selectedPath: string;
}) {
  if (node.children) {
    return (
      <TreeItem itemType="branch">
        <TreeItemLayout
          iconBefore={<Folder20Regular />}
          style={{ fontWeight: 500 }}
        >
          {node.name}
        </TreeItemLayout>
        <Tree>
          {node.children.map((child) => (
            <FileTreeItem
              key={child.path || child.name}
              node={child}
              onSelect={onSelect}
              selectedPath={selectedPath}
            />
          ))}
        </Tree>
      </TreeItem>
    );
  }

  return (
    <TreeItem
      itemType="leaf"
      onClick={() => node.path && onSelect(node.path)}
      style={{
        cursor: "pointer",
        background: node.path === selectedPath ? "rgba(0,120,212,0.08)" : undefined,
        borderRadius: 4,
      }}
    >
      <TreeItemLayout iconBefore={<Document20Regular />}>
        {node.name}
      </TreeItemLayout>
    </TreeItem>
  );
}

export function ProjectExplorer() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const basePath = params.get("path") || "";
  const groupId = params.get("id") || "";

  const [allOutputs, setAllOutputs] = useState<OutputFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedFile, setSelectedFile] = useState("");
  const [fileContent, setFileContent] = useState("");
  const [fileLoading, setFileLoading] = useState(false);

  // Detect the project root directory (fallback when no group id)
  const projectDir = useMemo(() => {
    const parts = basePath.replace(/\/$/, "").split("/");
    if (parts[parts.length - 1]?.includes(".")) parts.pop();
    return parts.join("/");
  }, [basePath]);

  const [resolvedName, setResolvedName] = useState("");
  const projectName = resolvedName || projectDir.split("/").pop() || "Project";

  useEffect(() => {
    setLoading(true);

    // If we have a group id, use its file list for precise scoping
    const groupedPromise = groupId
      ? listGroupedOutputs().then((groups) => groups.find((g) => g.id === groupId))
      : Promise.resolve(undefined);

    Promise.all([listOutputs(), groupedPromise])
      .then(([outputs, group]) => {
        let filtered: OutputFile[];
        if (group) {
          // Use the exact file list from the grouped output
          const fileSet = new Set(group.files);
          filtered = outputs.filter((o) => fileSet.has(o.path));
          if (group.title) setResolvedName(group.title);
        } else {
          // Fallback: directory prefix match
          filtered = outputs.filter((o) => o.path.startsWith(projectDir));
        }
        setAllOutputs(filtered);

        // Auto-select README.md if it exists, then primary_file, then first file
        // Prefer the shallowest README.md (root of the project, not nested)
        const readmes = filtered.filter(
          (o) => o.name.toLowerCase() === "readme.md",
        );
        const readme = readmes.length > 0
          ? readmes.reduce((a, b) =>
              a.path.split("/").length <= b.path.split("/").length ? a : b,
            )
          : undefined;
        const primary = filtered.find((o) => o.path === basePath);
        if (readme) {
          setSelectedFile(readme.path);
        } else if (primary) {
          setSelectedFile(primary.path);
        } else if (filtered.length > 0) {
          setSelectedFile(filtered[0].path);
        }

        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [projectDir, groupId, basePath]);

  // Escape to close
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") navigate("/library");
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [navigate]);

  useEffect(() => {
    if (!selectedFile) return;
    setFileLoading(true);
    readFile(selectedFile)
      .then((r) => {
        setFileContent(r.content);
        setFileLoading(false);
      })
      .catch(() => setFileLoading(false));
  }, [selectedFile]);

  const tree = useMemo(
    () => buildTree(allOutputs, projectDir),
    [allOutputs, projectDir],
  );

  const isMarkdown = selectedFile.endsWith(".md");
  const isDrawio = selectedFile.endsWith(".drawio");

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 80 }}>
        <Spinner label="Loading project..." size="large" />
      </div>
    );
  }

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      {/* File tree */}
      <div
        style={{
          width: 260,
          borderRight: "1px solid var(--border)",
          overflowY: "auto",
          background: "var(--card-bg)",
          flexShrink: 0,
          padding: "16px 0",
        }}
      >
        <div
          style={{
            padding: "0 12px 12px",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <FolderOpen20Regular style={{ color: "var(--brand-primary)" }} />
          <Text weight="semibold" size={300} style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {projectName}
          </Text>
        </div>
        <Tree aria-label="File tree">
          {tree.map((node) => (
            <FileTreeItem
              key={node.path || node.name}
              node={node}
              onSelect={setSelectedFile}
              selectedPath={selectedFile}
            />
          ))}
        </Tree>
      </div>

      {/* Content area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* Header bar */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "12px 24px",
            borderBottom: "1px solid var(--border)",
            background: "var(--card-bg)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <Button
              appearance="subtle"
              icon={<ArrowLeft20Regular />}
              onClick={() => navigate("/library")}
            >
              Back to Library
            </Button>
            <Text size={300} style={{ color: "var(--text-secondary)" }}>
              {selectedFile.split("/").pop() || ""}
            </Text>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <Button
              appearance="primary"
              icon={<ArrowDownload20Regular />}
              size="small"
              onClick={async () => {
                try {
                  const res = await fetch("/outputs/zip", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ paths: [projectDir], name: projectName }),
                  });
                  if (!res.ok) throw new Error(`HTTP ${res.status}`);
                  const blob = await res.blob();
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `${projectName}.zip`;
                  a.click();
                  URL.revokeObjectURL(url);
                } catch (e: any) {
                  alert(`ZIP failed: ${e.message}`);
                }
              }}
            >
              Download ZIP
            </Button>
            {window.csaStudio && (
              <Button
                appearance="outline"
                size="small"
                onClick={() => window.csaStudio?.openInVSCode(projectDir)}
              >
                Open in VS Code
              </Button>
            )}
            <Button
              appearance="subtle"
              icon={<Delete20Regular />}
              size="small"
              onClick={async () => {
                if (!confirm(`Delete "${projectName}" and all its files? This cannot be undone.`)) return;
                try {
                  await fetch(`/outputs?path=${encodeURIComponent(projectDir)}`, { method: "DELETE" });
                  navigate("/library");
                } catch (e) {
                  alert("Failed to delete");
                }
              }}
              style={{ color: "#d13438" }}
            >
              Delete
            </Button>
          </div>
        </div>

        {/* File content */}
        <div style={{ flex: 1, overflowY: "auto", background: "var(--card-bg)" }}>
          {fileLoading ? (
            <div
              style={{
                display: "flex",
                justifyContent: "center",
                padding: 48,
              }}
            >
              <Spinner size="small" />
            </div>
          ) : isDrawio ? (
            <DrawioRenderer xml={fileContent} />
          ) : isMarkdown ? (
            <div
              className="md-content"
              style={{ padding: "24px 40px 60px", maxWidth: 840, margin: "0 auto" }}
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeHighlight]}
              >
                {fileContent.replace(/<!--[\s\S]*?-->/g, "")}
              </ReactMarkdown>
            </div>
          ) : (
            <pre style={{ margin: 0, borderRadius: 0, minHeight: "100%" }}>
              <code>{fileContent}</code>
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}
