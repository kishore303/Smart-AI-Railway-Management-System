export interface NotificationItem {
  id: number;
  type: string;
  title: string;
  message: string;
  priority: string;
  is_read: boolean;
  created_at: string | null;
}

export interface NotificationListResponse {
  total: number;
  items: NotificationItem[];
  skip: number;
  limit: number;
}

export type WsStatus = "CONNECTED" | "CONNECTING" | "DISCONNECTED" | "RECONNECTING";

export interface WsNotificationEvent {
  type: "notification";
  notification_id: number;
  event: string;
  title: string;
  message: string;
  priority: string;
  created_at: string | null;
}

export function isWsNotificationEvent(v: unknown): v is WsNotificationEvent {
  if (typeof v !== "object" || v === null) return false;
  const o = v as Record<string, unknown>;
  return o.type === "notification" && typeof o.notification_id === "number";
}

export function priorityBadgeKind(priority: string): "green" | "amber" | "red" | "blue" {
  if (priority === "HIGH" || priority === "CRITICAL" || priority === "EMERGENCY") return "red";
  if (priority === "NORMAL") return "blue";
  return "amber";
}
