const WS_BASE =
  import.meta.env.VITE_WS_URL ||
  `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`;

const API_TOKEN = (import.meta.env.VITE_API_TOKEN as string | undefined) || "";

function withToken(path: string): string {
  if (!API_TOKEN) return path;
  const sep = path.includes("?") ? "&" : "?";
  return `${path}${sep}token=${encodeURIComponent(API_TOKEN)}`;
}

export function connectStream<T>(
  path: string,
  onMessage: (data: T) => void,
  onStatusChange?: (connected: boolean) => void
) {
  let socket: WebSocket | null = null;
  let closedByUser = false;
  let retryDelay = 1000;

  function open() {
    socket = new WebSocket(`${WS_BASE}${withToken(path)}`);
    socket.onopen = () => {
      retryDelay = 1000;
      onStatusChange?.(true);
    };
    socket.onmessage = (event) => {
      try {
        onMessage(JSON.parse(event.data));
      } catch {
        /* ignore malformed frame */
      }
    };
    socket.onclose = () => {
      onStatusChange?.(false);
      if (!closedByUser) {
        setTimeout(open, retryDelay);
        retryDelay = Math.min(retryDelay * 1.5, 10000);
      }
    };
    socket.onerror = () => {
      socket?.close();
    };
  }

  open();

  return () => {
    closedByUser = true;
    socket?.close();
  };
}
