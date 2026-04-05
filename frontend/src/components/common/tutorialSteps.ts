export interface TutorialStep {
  /** CSS selector for the element to spotlight (or null for centered modal) */
  target: string | null;
  /** Title shown in the tooltip card */
  title: string;
  /** Description text */
  description: string;
  /** Where to place the tooltip relative to the target */
  placement: "top" | "bottom" | "left" | "right" | "center";
  /** Accent color for the step */
  color?: string;
}

export const TUTORIAL_STEPS: TutorialStep[] = [
  {
    target: null,
    title: "Welcome to CSA Copilot",
    description:
      "Your AI-powered content factory for Microsoft Cloud Solution Architects. " +
      "Let's take a quick tour of the interface — it only takes a minute.",
    placement: "center",
    color: "#0078D4",
  },
  {
    target: "[data-tutorial='sidebar-nav']",
    title: "Sidebar Navigation",
    description:
      "This is your main navigation hub. Jump between the Launchpad, Mission Control, " +
      "Library, and Settings. You can collapse it for more workspace.",
    placement: "right",
    color: "#0078D4",
  },
  {
    target: "[data-tutorial='launchpad-hero']",
    title: "The Launchpad",
    description:
      "Your starting point. Pick a content tool or AI workflow to begin building " +
      "presentations, demos, hackathons, or full AI projects.",
    placement: "bottom",
    color: "#0078D4",
  },
  {
    target: "[data-tutorial='content-tools']",
    title: "Content Tools",
    description:
      "Three powerful conductors: Slides, Demos, and Hackathons. Click any card to configure " +
      "your brief — topic, content level, duration — and let the AI build it.",
    placement: "bottom",
    color: "#00A4EF",
  },
  {
    target: "[data-tutorial='ai-workflow']",
    title: "AI Project Workflow",
    description:
      "A step-by-step pipeline: Brainstorm ideas, architect a solution, implement it, then " +
      "generate demo presentations. Each step builds on the previous one.",
    placement: "top",
    color: "#8661C5",
  },
  {
    target: "[data-tutorial='nav-mission']",
    title: "Mission Control",
    description:
      "Track all running and completed jobs in real time. See progress, token usage, " +
      "and manage active agent sessions from one unified dashboard.",
    placement: "right",
    color: "#F25022",
  },
  {
    target: "[data-tutorial='nav-library']",
    title: "Output Library",
    description:
      "All generated content lives here — slide decks, demo guides, hackathon packages, " +
      "and AI project artifacts. Preview, download, or revisit anytime.",
    placement: "right",
    color: "#7FBA00",
  },
  {
    target: "[data-tutorial='nav-settings']",
    title: "Settings",
    description:
      "Configure your backend connection, choose your theme, and customize your experience.",
    placement: "right",
    color: "#FFB900",
  },
  {
    target: null,
    title: "You're all set!",
    description:
      "Head to the Launchpad and create your first piece of content. You can always " +
      "revisit this tutorial from the sidebar — look for the \"Tutorial\" link.",
    placement: "center",
    color: "#7FBA00",
  },
];
