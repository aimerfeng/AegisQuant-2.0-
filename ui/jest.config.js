module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'jsdom',
  roots: ['<rootDir>/src'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/renderer/$1',
    '^@components/(.*)$': '<rootDir>/src/renderer/components/$1',
    '^@services/(.*)$': '<rootDir>/src/renderer/services/$1',
    '^@stores/(.*)$': '<rootDir>/src/renderer/stores/$1',
    '^@utils/(.*)$': '<rootDir>/src/renderer/utils/$1',
    '^@types/(.*)$': '<rootDir>/src/renderer/types/$1',
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
  },
  setupFilesAfterEnv: ['<rootDir>/src/setupTests.ts'],
  testMatch: ['**/__tests__/**/*.ts?(x)', '**/?(*.)+(spec|test).ts?(x)'],
  transform: {
    '^.+\\.tsx?$': 'ts-jest',
  },
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json', 'node'],
};
