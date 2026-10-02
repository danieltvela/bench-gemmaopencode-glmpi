import { tool } from "@opencode-ai/plugin"

const IMAGE = "swift:6.1-jammy"

export default tool({
  description:
    "Run a SwiftPM command (build, test, package resolve, run, ...) inside the pinned " +
    "swift:6.1-jammy Docker image, with the current directory mounted at /ws. " +
    "The host has no Swift toolchain, so use this instead of calling swift directly.",
  args: {
    args: tool.schema
      .array(tool.schema.string())
      .describe('Swift arguments, e.g. ["build"] or ["test"] or ["package","resolve"]'),
    timeoutMs: tool.schema
      .number()
      .optional()
      .describe("Optional timeout in milliseconds (default 900000)"),
  },
  async execute(args, context) {
    const timeoutMs = args.timeoutMs ?? 900000
    const argv = [
      "docker", "run", "--rm",
      "-v", `${context.directory}:/ws`,
      "-w", "/ws",
      "-e", "HOME=/tmp",
      IMAGE,
      "swift",
      ...(args.args ?? []),
    ]
    const proc = Bun.spawn(argv, {
      cwd: context.directory,
      stdout: "pipe",
      stderr: "pipe",
    })
    const timer = setTimeout(() => proc.kill(), timeoutMs)
    try {
      const [stdout, stderr] = await Promise.all([
        new Response(proc.stdout).text(),
        new Response(proc.stderr).text(),
      ])
      const code = await proc.exited
      const output = [stdout, stderr].filter(Boolean).join("\n").trim()
      const tail = output.length > 20000 ? output.slice(-20000) : output
      const label = `swift ${(args.args ?? []).join(" ")}`
      return code === 0 ? `${label}: ok\n${tail}` : `${label}: exit ${code}\n${tail}`
    } finally {
      clearTimeout(timer)
    }
  },
})
