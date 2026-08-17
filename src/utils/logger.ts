export class Logger {
  private logs: string[] = [];

  info(msg: string) {
    const formatted = `[INFO] ${msg}`;
    this.logs.push(formatted);
    console.log(formatted);
  }

  warning(msg: string) {
    const formatted = `[WARN] ${msg}`;
    this.logs.push(formatted);
    console.warn(formatted);
  }

  error(msg: string) {
    const formatted = `[ERROR] ${msg}`;
    this.logs.push(formatted);
    console.error(formatted);
  }

  getLogs(): string[] {
    return [...this.logs];
  }

  flush(): string[] {
    const current = [...this.logs];
    this.logs = [];
    return current;
  }
}

export function configurar_logger(): Logger {
  return new Logger();
}
