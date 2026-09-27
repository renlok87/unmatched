// GD-034: create/rotate the two scoped demo accounts for the combat demo.
// Random passwords are written to backend/.env (gitignored) as
// S09_DEMO_HOST_EMAIL/PASSWORD and S09_DEMO_JOINER_EMAIL/PASSWORD - never
// printed, never on any command line.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
// Resolve against backend/node_modules (script lives in tools/s09).
const backendModules = path.resolve(__dirname, '..', '..', 'backend', 'node_modules');
const bcrypt = require(path.join(backendModules, 'bcrypt'));
const { PrismaClient } = require(path.join(backendModules, '@prisma', 'client'));

for (const line of fs.readFileSync(path.resolve(__dirname, '..', '..', 'backend', '.env'), 'utf8').split(/\r?\n/)) {
  const m = line.match(/^([A-Z_]+)=(.*)$/);
  if (m && !process.env[m[1]]) process.env[m[1]] = m[2];
}

const prisma = new PrismaClient();
const envPath = path.resolve(__dirname, '..', '..', 'backend', '.env');

async function upsert(email) {
  const password = crypto.randomBytes(18).toString('hex');
  const hash = await bcrypt.hash(password, 10);
  await prisma.user.upsert({
    where: { email },
    update: { password: hash, emailVerified: new Date() },
    create: { email, username: email.split('@')[0], password: hash, emailVerified: new Date() },
  });
  return password;
}

function setEnv(keys) {
  const lines = fs.readFileSync(envPath, 'utf8').split(/\r?\n/);
  for (const [key, value] of Object.entries(keys)) {
    const prefix = `${key}=`;
    const index = lines.findIndex((line) => line.startsWith(prefix));
    if (index >= 0) lines[index] = prefix + value;
    else lines.push(prefix + value);
  }
  fs.writeFileSync(envPath, lines.join('\n'), 'utf8');
}

async function main() {
  const host = await upsert('s09-gd034-host@test.local');
  const joiner = await upsert('s09-gd034-joiner@test.local');
  setEnv({
    S09_DEMO_HOST_EMAIL: 's09-gd034-host@test.local',
    S09_DEMO_HOST_PASSWORD: host,
    S09_DEMO_JOINER_EMAIL: 's09-gd034-joiner@test.local',
    S09_DEMO_JOINER_PASSWORD: joiner,
  });
  console.log('demo accounts ready; credentials stored in backend/.env');
}

main()
  .catch((e) => { console.error('FAILED:', e.message); process.exit(1); })
  .finally(() => prisma.$disconnect());
