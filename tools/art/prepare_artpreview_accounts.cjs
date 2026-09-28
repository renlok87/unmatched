// Create two scoped art-preview accounts in the isolated S09 test database.
// Passwords stay in this worktree's ignored backend/.env; no credentials are
// printed or put on a command line. Existing S09 demo accounts are untouched.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const root = path.resolve(__dirname, '../..');
const envPath = path.join(root, 'backend', '.env');
require(path.join(root, 'backend', 'node_modules', 'dotenv')).config({ path: envPath });
const db = new URL(process.env.DATABASE_URL || 'postgresql://invalid');
if (!['localhost', '127.0.0.1'].includes(db.hostname) || db.port !== '55434') {
  throw new Error('Art-preview accounts require the isolated S09 database on port 55434');
}
const bcrypt = require(path.join(root, 'backend', 'node_modules', 'bcrypt'));
const { PrismaClient } = require(path.join(root, 'backend', 'node_modules', '@prisma', 'client'));
const prisma = new PrismaClient();

async function upsert(email) {
  const password = crypto.randomBytes(24).toString('hex');
  const hash = await bcrypt.hash(password, 10);
  await prisma.user.upsert({
    where: { email },
    update: { password: hash, emailVerified: new Date() },
    create: { email, username: email.split('@')[0], password: hash, emailVerified: new Date() },
  });
  return password;
}

async function main() {
  const host = 'art-preview-host@test.local';
  const joiner = 'art-preview-joiner@test.local';
  const hostPassword = await upsert(host);
  const joinerPassword = await upsert(joiner);
  const values = {
    S08_DEMO_HOST_EMAIL: host,
    S08_DEMO_HOST_PASSWORD: hostPassword,
    S08_DEMO_JOINER_EMAIL: joiner,
    S08_DEMO_JOINER_PASSWORD: joinerPassword,
  };
  const lines = fs.readFileSync(envPath, 'utf8').split(/\r?\n/).filter(Boolean);
  for (const [key, value] of Object.entries(values)) {
    const i = lines.findIndex((line) => line.startsWith(`${key}=`));
    if (i >= 0) lines[i] = `${key}=${value}`;
    else lines.push(`${key}=${value}`);
  }
  fs.writeFileSync(envPath, lines.join('\n') + '\n', 'utf8');
  console.log('ARTPREVIEW_ACCOUNTS_READY: credentials stored in ignored worktree backend/.env');
}

main().catch((error) => {
  console.error('ARTPREVIEW_ACCOUNTS_FAILED:', error.message);
  process.exitCode = 1;
}).finally(() => prisma.$disconnect());
