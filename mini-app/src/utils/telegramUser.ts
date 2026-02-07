/**
 * Извлечение данных пользователя Telegram для автозаполнения.
 * initDataUnsafe не всегда заполняется клиентом — парсим сырую строку initData.
 */

export interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
}

/**
 * Парсит initData (query string) и возвращает объект user или null.
 * Проверку подписи не делаем — только извлечение для отображения; бэкенд валидирует.
 */
function parseUserFromInitData(initData: string): TelegramUser | null {
  if (!initData || !initData.trim()) return null;
  try {
    const params = new URLSearchParams(initData);
    const userStr = params.get("user");
    if (!userStr) return null;
    const raw = decodeURIComponent(userStr);
    const obj = JSON.parse(raw) as unknown;
    if (!obj || typeof obj !== "object" || typeof (obj as { first_name?: unknown }).first_name !== "string")
      return null;
    const u = obj as { id?: number; first_name: string; last_name?: string; username?: string };
    return {
      id: typeof u.id === "number" ? u.id : 0,
      first_name: u.first_name,
      last_name: typeof u.last_name === "string" ? u.last_name : undefined,
      username: typeof u.username === "string" ? u.username : undefined,
    };
  } catch {
    return null;
  }
}

/**
 * Возвращает имя для отображения (first_name + last_name).
 * Источник: initDataUnsafe.user, иначе парсинг initData.
 */
export function getTelegramDisplayName(): string {
  const tw = typeof window !== "undefined" ? window.Telegram?.WebApp : undefined;
  const fromUnsafe = tw?.initDataUnsafe?.user;
  const parts: string[] = [];
  if (fromUnsafe) {
    if (fromUnsafe.first_name) parts.push(fromUnsafe.first_name);
    if (fromUnsafe.last_name) parts.push(fromUnsafe.last_name);
  }
  if (parts.length) return parts.join(" ").trim();

  const raw = tw?.initData;
  if (raw) {
    const parsed = parseUserFromInitData(raw);
    if (parsed) {
      if (parsed.first_name) parts.push(parsed.first_name);
      if (parsed.last_name) parts.push(parsed.last_name);
      if (parts.length) return parts.join(" ").trim();
    }
  }
  return "";
}
