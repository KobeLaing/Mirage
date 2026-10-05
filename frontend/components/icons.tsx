// Original icon set for Mirage. Simple geometric line art drawn for this app.

interface IconProps {
  className?: string;
  title?: string;
}

function svgProps({ className, title }: IconProps) {
  return {
    className,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": title ? undefined : true,
    role: title ? "img" : undefined,
  };
}

/** "AI" vote: a small square robot. */
export function RobotIcon(props: IconProps) {
  return (
    <svg {...svgProps(props)}>
      {props.title && <title>{props.title}</title>}
      <path d="M12 3v3" />
      <circle cx="12" cy="2.6" r="1" fill="currentColor" stroke="none" />
      <rect x="4.5" y="6" width="15" height="13" rx="3" />
      <rect x="8" y="10" width="2.2" height="3" rx="1.1" fill="currentColor" stroke="none" />
      <rect x="13.8" y="10" width="2.2" height="3" rx="1.1" fill="currentColor" stroke="none" />
      <path d="M9.5 16h5" />
      <path d="M2.5 11v3M21.5 11v3" />
    </svg>
  );
}

/** "Real" vote: a check mark inside a circle. */
export function CheckCircleIcon(props: IconProps) {
  return (
    <svg {...svgProps(props)}>
      {props.title && <title>{props.title}</title>}
      <circle cx="12" cy="12" r="9" />
      <path d="M7.8 12.3l2.8 2.8 5.6-6" />
    </svg>
  );
}

export function HeartIcon(props: IconProps) {
  return (
    <svg {...svgProps(props)}>
      {props.title && <title>{props.title}</title>}
      <path d="M12 19.5s-7-4.3-7-9.6A3.9 3.9 0 0 1 12 7.6a3.9 3.9 0 0 1 7 2.3c0 5.3-7 9.6-7 9.6z" />
    </svg>
  );
}

/** "Like": an upward spark arrow, not a thumb. */
export function LikeIcon(props: IconProps) {
  return (
    <svg {...svgProps(props)}>
      {props.title && <title>{props.title}</title>}
      <path d="M12 19V7" />
      <path d="M7 11.5L12 6l5 5.5" />
      <path d="M4.5 5.5l1.5 1M19.5 5.5l-1.5 1M12 2.5v1" />
    </svg>
  );
}

export function LaughIcon(props: IconProps) {
  return (
    <svg {...svgProps(props)}>
      {props.title && <title>{props.title}</title>}
      <circle cx="12" cy="12" r="9" />
      <path d="M7.8 10.2l1.6-1.2 1.6 1.2M13 10.2l1.6-1.2 1.6 1.2" />
      <path d="M7.5 13.5h9a4.5 4.5 0 0 1-9 0z" fill="currentColor" fillOpacity="0.25" />
    </svg>
  );
}

export function SmileOutlineIcon(props: IconProps) {
  return (
    <svg {...svgProps(props)}>
      {props.title && <title>{props.title}</title>}
      <circle cx="12" cy="12" r="9" />
      <path d="M9 10h.01M15 10h.01" />
      <path d="M8.5 14.5a4.5 4.5 0 0 0 7 0" />
    </svg>
  );
}

export function TrashIcon(props: IconProps) {
  return (
    <svg {...svgProps(props)}>
      {props.title && <title>{props.title}</title>}
      <path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3" />
    </svg>
  );
}

export function UploadIcon(props: IconProps) {
  return (
    <svg {...svgProps(props)}>
      {props.title && <title>{props.title}</title>}
      <path d="M12 16V4M7 9l5-5 5 5" />
      <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
    </svg>
  );
}

export function PencilIcon(props: IconProps) {
  return (
    <svg {...svgProps(props)}>
      {props.title && <title>{props.title}</title>}
      <path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16v4z" />
      <path d="M13.5 6.5l4 4" />
    </svg>
  );
}

export function CloseIcon(props: IconProps) {
  return (
    <svg {...svgProps(props)}>
      {props.title && <title>{props.title}</title>}
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  );
}
