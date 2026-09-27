// S09 worktree-local backend launcher (hidden window, env-driven config).
require('dotenv').config({ path: '.env' });
process.env.NODE_ENV = 'development';
require('./dist/src/main.js');
