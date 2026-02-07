/**
 * Haptic feedback утилиты для Telegram Mini App
 */

export const haptic = {
  light: () => {
    window.Telegram?.WebApp?.HapticFeedback?.impactOccurred("light");
  },
  medium: () => {
    window.Telegram?.WebApp?.HapticFeedback?.impactOccurred("medium");
  },
  success: () => {
    window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred("success");
  },
  error: () => {
    window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred("error");
  },
  selection: () => {
    window.Telegram?.WebApp?.HapticFeedback?.selectionChanged();
  },
};
