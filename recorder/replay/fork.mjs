// Usage: node fork.mjs --session-id ID --message-id ID --model M --message-file F --out DIR --restore-cmd CMD [--timeout SEC]
// Needs RETRACE_CONTAINER and FACTORY_API_KEY. Writes DIR/fork.json.
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  AutonomyLevel,
  DroidMessageType,
  ToolConfirmationOutcome,
  resumeSession,
} from '@factory/droid-sdk/node';

const args = {};
for (let i = 2; i < process.argv.length; i += 2) args[process.argv[i].replace(/^--/, '')] = process.argv[i + 1];
for (const k of ['session-id', 'message-id', 'model', 'message-file', 'out', 'restore-cmd']) {
  if (!args[k]) throw new Error(`missing --${k}`);
}

const out = {
  source_session_id: args['session-id'],
  message_id: args['message-id'],
  message: readFileSync(args['message-file'], 'utf8'),
  timed_out: false,
};
const flush = () => writeFileSync(join(args.out, 'fork.json'), JSON.stringify(out, null, 2) + '\n');
const log = (m) => console.error(`[fork] ${m}`);

const session = await resumeSession(args['session-id'], {
  execPath: join(dirname(fileURLToPath(import.meta.url)), 'docker-droid.sh'),
  permissionHandler: () => ToolConfirmationOutcome.ProceedOnce,
});
out.resumed_cwd = session.cwd;
log(`resumed ${session.id} cwd ${session.cwd}`);

const info = await session.getRewindInfo({ messageId: args['message-id'] });
out.rewind_info = {
  available_files: info.availableFiles.length,
  created_files: info.createdFiles.length,
  evicted_files: info.evictedFiles,
};
log(`rewind info ${JSON.stringify(out.rewind_info)}`);

const { session: fork } = await session.rewind({
  messageId: args['message-id'],
  filesToRestore: info.availableFiles,
  filesToDelete: info.createdFiles,
  forkTitle: `retrace ${args['message-id']}`,
});
out.successor_session_id = fork.id;
out.successor_cwd = fork.cwd;
log(`successor ${fork.id} cwd ${fork.cwd}`);

execFileSync('sh', ['-c', args['restore-cmd']], { stdio: ['ignore', 2, 2] });

await fork.updateSettings({ modelId: args.model, autonomyLevel: AutonomyLevel.High });
out.model = fork.settings.modelId;
flush();

const timer = setTimeout(() => {
  out.timed_out = true;
  log('timeout, interrupting');
  fork.interrupt().catch(() => {});
  setTimeout(() => {
    flush();
    process.exit(124);
  }, 60000).unref();
}, Number(args.timeout ?? 1800) * 1000);

const updates = [];
let result;
for await (const m of fork.stream(out.message, { includePartialMessages: true })) {
  if (m.type === 'token_usage_update') updates.push(m);
  if (m.type === DroidMessageType.Result) result = m;
}
clearTimeout(timer);
out.token_updates = { count: updates.length, first: updates[0] ?? null, last: updates.at(-1) ?? null };
if (result) {
  out.success = result.success;
  out.subtype = result.subtype;
  out.duration_ms = result.durationMs;
  out.turn_count = result.turnCount;
  out.token_usage = result.tokenUsage;
  out.cost_credits = result.tokenUsage?.factoryCredits ?? null;
  out.text = result.text;
  out.error = result.error;
}
flush();
await fork.close();
