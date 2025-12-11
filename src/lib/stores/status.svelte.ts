/**
 * Global status store for app-wide notifications and file tracking.
 * Uses Svelte 5 runes for reactivity.
 */

export type LogLevel = 'info' | 'success' | 'warning' | 'error';

export interface LogEntry {
  id: string;
  message: string;
  level: LogLevel;
  timestamp: Date;
  module?: string;
}

export interface OpenFile {
  path: string;
  name: string;
  module: string;
}

// State
let currentStatus = $state<string>('Ready');
let currentLevel = $state<LogLevel>('info');
let logs = $state<LogEntry[]>([]);
let openFiles = $state<OpenFile[]>([]);
let isExpanded = $state(false);

// Max log entries to keep
const MAX_LOGS = 100;

/**
 * Add a log entry and update current status
 */
export function log(message: string, level: LogLevel = 'info', module?: string) {
  const entry: LogEntry = {
    id: `log-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
    message,
    level,
    timestamp: new Date(),
    module,
  };

  logs = [entry, ...logs].slice(0, MAX_LOGS);
  currentStatus = message;
  currentLevel = level;
}

/**
 * Shorthand for success log
 */
export function logSuccess(message: string, module?: string) {
  log(message, 'success', module);
}

/**
 * Shorthand for error log
 */
export function logError(message: string, module?: string) {
  log(message, 'error', module);
}

/**
 * Shorthand for warning log
 */
export function logWarning(message: string, module?: string) {
  log(message, 'warning', module);
}

/**
 * Register an open file
 */
export function registerFile(path: string, name: string, module: string) {
  // Remove existing file from same module
  openFiles = openFiles.filter(f => f.module !== module || f.path !== path);
  openFiles = [...openFiles, { path, name, module }];
}

/**
 * Unregister a file
 */
export function unregisterFile(path: string, module: string) {
  openFiles = openFiles.filter(f => !(f.path === path && f.module === module));
}

/**
 * Unregister all files from a module
 */
export function unregisterModule(module: string) {
  openFiles = openFiles.filter(f => f.module !== module);
}

/**
 * Toggle log panel expansion
 */
export function toggleExpanded() {
  isExpanded = !isExpanded;
}

/**
 * Set expansion state
 */
export function setExpanded(value: boolean) {
  isExpanded = value;
}

/**
 * Clear all logs
 */
export function clearLogs() {
  logs = [];
  currentStatus = 'Ready';
  currentLevel = 'info';
}

/**
 * Get reactive status state
 */
export function getStatus() {
  return {
    get current() { return currentStatus; },
    get level() { return currentLevel; },
    get logs() { return logs; },
    get openFiles() { return openFiles; },
    get isExpanded() { return isExpanded; },
    get fileCount() { return openFiles.length; },
    get fileNames() { return openFiles.map(f => f.name); },
  };
}
