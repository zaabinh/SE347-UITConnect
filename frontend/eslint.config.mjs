import { FlatCompat } from '@eslint/eslintrc';
import { createRequire } from 'node:module';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const compat = new FlatCompat({
  baseDirectory: fileURLToPath(new URL('.', import.meta.url)),
  resolvePluginsRelativeTo: dirname(require.resolve('eslint-config-next')),
});

export default [...compat.extends('next/core-web-vitals')];
