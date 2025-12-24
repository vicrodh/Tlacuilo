// Debug logging store with visual overlay support
// Toggle via Settings

interface LogEntry {
  id: number;
  timestamp: Date;
  level: 'info' | 'warn' | 'error' | 'debug';
  source: string;
  message: string;
  data?: unknown;
}

let logs = $state<LogEntry[]>([]);
let enabled = $state(false); // Disabled to test if logging causes the loop
let nextId = 0;
const MAX_LOGS = 100;

export function debugLog(source: string, message: string, data?: unknown, level: LogEntry['level'] = 'info') {
  if (!enabled) return;

  const entry: LogEntry = {
    id: nextId++,
    timestamp: new Date(),
    level,
    source,
    message,
    data,
  };

  // Also log to console with color coding
  const prefix = `[${entry.timestamp.toLocaleTimeString()}.${entry.timestamp.getMilliseconds().toString().padStart(3, '0')}] [${source}]`;

  switch (level) {
    case 'error':
      console.error(prefix, message, data ?? '');
      break;
    case 'warn':
      console.warn(prefix, message, data ?? '');
      break;
    case 'debug':
      console.debug(prefix, message, data ?? '');
      break;
    default:
      console.log(prefix, message, data ?? '');
  }

  logs = [...logs.slice(-(MAX_LOGS - 1)), entry];
}

export function clearLogs() {
  logs = [];
}

export function setDebugEnabled(value: boolean) {
  enabled = value;
  if (value) {
    debugLog('DebugLog', 'Debug logging enabled');
  }
}

export function getDebugLogs() {
  return logs;
}

export function isDebugEnabled() {
  return enabled;
}

// Reactive getters for Svelte components
export const debugLogStore = {
  get logs() { return logs; },
  get enabled() { return enabled; },
};
