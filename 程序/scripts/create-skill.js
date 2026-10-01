#!/usr/bin/env node
'use strict';
/*
 * SKILL 文件模板生成器（第 28 期第 8 条）。
 *
 *   node scripts/create-skill.js            # 一路问答，回车取默认值
 *   node scripts/create-skill.js --name firstframe-retry --stage 首帧管理 --yes
 *
 * 生成的 .skill.md 与 skills/ 下现有 20 个文件同一个形状：YAML frontmatter 固定 17 个字段，
 * 正文一段「## 说明」。feedback 默认就是「三虎」那三条（进度／异常／收尾）——集成后所有 UI、
 * 通知、日志都用「三虎」，生成器不该让新 SKILL 漏掉这一条。
 *
 * 写完不重启也认：skill_registry.Registry 每次查询前比 mtime 与大小，新文件下一趟就进表。
 */
const fs = require('fs');
const path = require('path');
const readline = require('readline');

const STAGES = ['剧本准备', '初步分镜', '资产管理', '分镜定稿', '首帧管理',
                '白模预演', '视频生成', '配音与字幕', '后期剪辑', '质检与交付'];
const CAPABILITIES = ['long-context', 'structured-output', 'creative-writing', 'reasoning', 'vision'];
const FEEDBACK = ['onProgress: 更新三虎进度', 'onError: 可重试自动重试', 'onComplete: 通知并推进阶段'];
const NAME_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const HERE = path.resolve(__dirname, '..');
const USAGE = [
  '用法：node scripts/create-skill.js [选项]',
  '  --name <id>            SKILL id（小写连字符，如 firstframe-retry）',
  '  --display <中文名>     界面上显示的名字',
  '  --description <说明>   一句话说明',
  '  --stage <阶段>         十个制作阶段之一（中文名或 id 都认）',
  '  --capabilities <列表>  逗号分隔，取值：' + CAPABILITIES.join(' / '),
  '  --preferred <列表>     首选模型，逗号分隔（可空）',
  '  --fallback <列表>      兜底模型，逗号分隔（可空）',
  '  --tools <列表>         子模块 API，逗号分隔',
  '  --depends <列表>       依赖的 SKILL id，逗号分隔',
  '  --conflicts <列表>     互斥的 SKILL id，逗号分隔',
  '  --input <列表>         输入字段，逗号分隔',
  '  --output <列表>        输出字段，逗号分隔',
  '  --constraints <列表>   约束说明，逗号分隔',
  '  --examples <列表>      示例（「用户：… → 调用…」），分号分隔',
  '  --paid / --free        是否付费步骤（默认免费）',
  '  --serial / --parallel  能不能并行（默认可并行）',
  '  --dir <目录>           输出目录（默认 ../skills）',
  '  --force                同名文件直接覆盖',
  '  --yes                  不再追问，缺的用默认值',
  '  -h, --help             看这页'
].join('\n');

function parseArgs(argv) {
  const out = { flags: {} };
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (token === '-h' || token === '--help') { out.flags.help = true; continue; }
    if (token === '--yes' || token === '--force' || token === '--paid' || token === '--free'
        || token === '--serial' || token === '--parallel') { out.flags[token.slice(2)] = true; continue; }
    if (token.startsWith('--')) { out[token.slice(2)] = argv[i + 1]; i += 1; }
  }
  return out;
}

function list(value) {
  return String(value || '').split(/[,，]/).map((item) => item.trim()).filter(Boolean);
}

function pickStage(value) {
  const text = String(value || '').trim();
  if (!text) return '';
  if (STAGES.includes(text)) return text;
  const ids = ['script', 'storyboard', 'assets', 'final', 'keyframe', 'previs', 'video', 'audio', 'edit', 'delivery'];
  const index = ids.indexOf(text.toLowerCase());
  return index >= 0 ? STAGES[index] : '';
}

function frontmatter(meta) {
  const rows = ['name: ' + meta.name, 'displayName: ' + meta.displayName,
    'description: ' + meta.description, 'stage: ' + meta.stage];
  const inline = (key, values) => rows.push(key + ': [' + values.join(', ') + ']');
  inline('capabilities', meta.capabilities);
  inline('preferredModels', meta.preferredModels);
  inline('fallbackModels', meta.fallbackModels);
  inline('tools', meta.tools);
  inline('dependsOn', meta.dependsOn);
  inline('conflictsWith', meta.conflictsWith);
  rows.push('parallelizable: ' + (meta.parallelizable ? 'true' : 'false'));
  rows.push('paid: ' + (meta.paid ? 'true' : 'false'));
  inline('input', meta.input);
  inline('output', meta.output);
  inline('constraints', meta.constraints);
  rows.push('feedback:');
  FEEDBACK.forEach((item) => rows.push('  - ' + item));
  rows.push('examples:');
  (meta.examples.length ? meta.examples : ['用户："跑一下这个 SKILL" → 按阶段配置里勾上的那几项'])
    .forEach((item) => rows.push('  - ' + item));
  return rows.join('\n');
}

function render(meta) {
  const body = [
    '', '## 说明', '',
    '本 SKILL 由「统一阶段配置面板」勾选后交给 SkillOrchestrator 执行；模型不写死在 SKILL 里，',
    '由 ModelRouter 按 capabilities、成本与可用性动态选（preferredModels 只是优先序，fallbackModels 兜底）。',
    '',
    '- 输入：' + (meta.input.join('、') || '无'),
    '- 输出：' + (meta.output.join('、') || '无'),
    '- 工具：' + (meta.tools.join('、') || '无'),
    '- 约束：' + (meta.constraints.join('、') || '无'),
    '- 示例：' + (meta.examples.join('；') || '无'),
    '- 反馈：界面进度走 onProgress，异常走 onError，收尾推进阶段走 onComplete。'
  ].join('\n');
  return '---\n' + frontmatter(meta) + '\n---\n' + body + '\n';
}

function reader(rl) {
  // 一行一行地问：pipe 进来的答案也一条都不丢。
  // rl.question 只在终端里可靠——数据整块灌进来时，'line' 事件会在提问之前先发完，
  // 后头的答案就没人接（pipe 管道测试时表现为「问了两句就没了」）。这里自己排队。
  const queue = [];
  const waiters = [];
  let closed = false;
  rl.on('line', (line) => (waiters.length ? waiters.shift()(line) : queue.push(line)));
  rl.on('close', () => {
    closed = true;
    while (waiters.length) waiters.shift()(null);
  });
  const echo = Boolean(process.stdin.isTTY);   // 管道里跑就别刷提示：答案是从文件喂进来的
  return function ask(question, fallback) {
    if (echo) process.stdout.write(fallback ? question + '（' + fallback + '）：' : question + '：');
    return new Promise((resolve) => {
      const take = (line) => {
        const text = line === null || line === undefined ? '' : String(line).trim();
        resolve(text || fallback || '');
      };
      if (queue.length) return take(queue.shift());
      if (closed) return take(null);
      return waiters.push(take);
    });
  };
}

async function collect(args) {
  const flags = args.flags;
  const meta = {
    name: args.name, displayName: args.display, description: args.description,
    stage: pickStage(args.stage), capabilities: list(args.capabilities),
    preferredModels: list(args.preferred), fallbackModels: list(args.fallback),
    tools: list(args.tools), dependsOn: list(args.depends), conflictsWith: list(args.conflicts),
    input: list(args.input), output: list(args.output), constraints: list(args.constraints),
    examples: String(args.examples || '').split(/[;；]/).map((item) => item.trim()).filter(Boolean),
    parallelizable: !flags.serial, paid: Boolean(flags.paid) && !flags.free
  };
  if (flags.help) return { meta, help: true };
  const givenPaid = Boolean(flags.paid || flags.free);
  const givenParallel = Boolean(flags.serial || flags.parallel);
  if (flags.yes) {
    meta.name = meta.name || 'new-skill';
    meta.displayName = meta.displayName || '新 SKILL';
    meta.description = meta.description || '一句话说明';
    meta.stage = meta.stage || STAGES[0];
    meta.capabilities = meta.capabilities.length ? meta.capabilities : ['structured-output'];
    if (!givenParallel) meta.parallelizable = true;
    if (!givenPaid) meta.paid = false;
    return { meta, help: false };
  }
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  const ask = reader(rl);
  try {
    meta.name = meta.name || await ask('SKILL id（小写连字符）', 'new-skill');
    meta.displayName = meta.displayName || await ask('中文名', '新 SKILL');
    meta.description = meta.description || await ask('一句话说明', '一句话说明');
    if (!meta.stage) meta.stage = pickStage(await ask('所属阶段（' + STAGES.join('/') + '）', STAGES[0]));
    if (!meta.capabilities.length) meta.capabilities = list(await ask('capabilities（逗号分隔）', 'structured-output'));
    if (!meta.tools.length) meta.tools = list(await ask('tools（子模块 API，逗号分隔）'));
    if (!meta.dependsOn.length) meta.dependsOn = list(await ask('dependsOn（依赖的 SKILL id，逗号分隔）'));
    if (!meta.input.length) meta.input = list(await ask('input（输入字段，逗号分隔）'));
    if (!meta.output.length) meta.output = list(await ask('output（输出字段，逗号分隔）'));
    if (!meta.constraints.length) meta.constraints = list(await ask('constraints（约束，逗号分隔）'));
    if (!givenPaid) meta.paid = /^y(es)?$/i.test(await ask('是付费步骤吗（y/N）', 'n'));
    if (!givenParallel) meta.parallelizable = !/^y(es)?$/i.test(await ask('不能并行吗（y/N）', 'n'));
  } finally {
    rl.close();
  }
  return { meta, help: false };
}

function validate(meta) {
  const problems = [];
  if (!NAME_RE.test(String(meta.name || ''))) problems.push('SKILL id 只能是小写字母、数字与连字符：' + meta.name);
  if (!meta.displayName) problems.push('缺中文名');
  if (!meta.stage) problems.push('所属阶段认不出（十个之一）');
  meta.capabilities.forEach((item) => {
    if (!CAPABILITIES.includes(item)) problems.push('capabilities 里有没登记的能力：' + item);
  });
  return problems;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const collected = await collect(args);
  if (collected.help) { console.log(USAGE); return 0; }
  const meta = collected.meta;
  const problems = validate(meta);
  if (problems.length) {
    problems.forEach((item) => console.error('× ' + item));
    console.error('\n' + USAGE);
    return 2;
  }
  const dir = path.resolve(HERE, args.dir || path.join('skills'));
  fs.mkdirSync(dir, { recursive: true });
  const target = path.join(dir, meta.name + '.skill.md');
  if (fs.existsSync(target) && !args.flags.force) {
    console.error('× 已经有这个 SKILL 了：' + target + '\n  要覆盖就加 --force。');
    return 3;
  }
  fs.writeFileSync(target, render(meta), 'utf8');
  console.log('已生成 ' + target);
  console.log('  阶段 ' + meta.stage + ' · ' + (meta.paid ? '付费' : '免费') + ' · '
    + (meta.parallelizable ? '可并行' : '串行'));
  console.log('  Registry 会热加载这一份：不用重启，下一次查询就进表。');
  return 0;
}

main().then((code) => { process.exitCode = code; }).catch((error) => {
  console.error('生成失败：' + (error && error.message ? error.message : error));
  process.exitCode = 1;
});