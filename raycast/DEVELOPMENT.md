# Development Guide

## Development Setup

### Prerequisites
- Node.js 18.x or higher
- npm or yarn
- Git

### Installation
```bash
# Install dependencies
npm install

# Set up git hooks (optional but recommended)
chmod +x .git/hooks/pre-commit
```

## Development Workflow

### Pre-commit Hooks
This project uses pre-commit hooks to ensure code quality. The following checks run automatically before each commit:

1. **ESLint** - Code linting and style checking
2. **Tests** - Unit and integration tests
3. **Build** - Ensures the project builds successfully

If any of these checks fail, the commit will be blocked until the issues are resolved.

### Manual Quality Checks
You can run these checks manually:

```bash
# Run linting
npm run lint

# Fix auto-fixable linting issues
npm run fix-lint

# Run tests
npm test

# Run tests in watch mode
npm test -- --watch

# Build the project
npm run build
```

## CI/CD Pipeline

### GitHub Actions
The project uses GitHub Actions for continuous integration. The CI pipeline runs on:

- **Push** to `main`, `develop`, or `tts-optimization` branches
- **Pull requests** to `main` or `develop` branches

#### CI Jobs
1. **Test Job** (runs on Node.js 18.x and 20.x)
   - Install dependencies
   - Run linting
   - Run tests
   - Build project

2. **Security Job** (runs after tests pass)
   - Security audit with `npm audit`

### Dependabot
Dependabot is configured to automatically:
- Update npm dependencies weekly (Mondays at 9:00 AM)
- Update GitHub Actions weekly (Mondays at 9:00 AM)
- Create pull requests with proper labels and assignees

## Code Quality Standards

### ESLint Configuration
The project uses a custom ESLint configuration based on Raycast's standards. Key rules:

- TypeScript strict mode enabled
- No `any` types allowed (use proper types)
- No unused variables
- Consistent code formatting

### Testing
- All new features must include tests
- Tests should be written using Vitest
- Aim for high test coverage
- Integration tests for critical paths

### Commit Messages
Follow conventional commit format:
```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

## Troubleshooting

### Pre-commit Hook Issues
If the pre-commit hook fails:

1. **Linting errors**: Run `npm run fix-lint` to auto-fix issues
2. **Test failures**: Fix failing tests before committing
3. **Build errors**: Ensure the project builds locally

### CI/CD Issues
If GitHub Actions fail:

1. Check the Actions tab in GitHub for detailed error logs
2. Ensure all tests pass locally
3. Verify linting passes locally
4. Check for dependency issues

### Common Issues

#### ESLint Errors
```bash
# Fix auto-fixable issues
npm run fix-lint

# Check specific files
npx eslint src/utils/tts/tts-processor.ts
```

#### Test Failures
```bash
# Run tests with verbose output
npm test -- --verbose

# Run specific test file
npm test -- src/utils/tts/tts-processor.test.ts
```

#### Build Issues
```bash
# Clean and rebuild
rm -rf dist/
npm run build
``` 