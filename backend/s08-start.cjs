require('dotenv').config({ path: '.env' });
process.env.NODE_ENV = 'development';
require('./dist/src/main.js');
