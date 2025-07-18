# Python 3.13 Compatibility Guide

## Overview

Python 3.13 introduces changes to the C API that cause compilation issues with some packages, particularly `blis` (a dependency of machine learning libraries). This document explains the compatibility issues and how they are resolved in this project.

## The Problem

When installing `misaki[en]` on Python 3.13, the installation fails with compilation errors in the `blis` package:

```
error: call to undeclared function '_PyInterpreterState_GetConfig'
error: call to undeclared function '_PyList_Extend'
error: too few arguments to function call, expected 6, have 5
```

These errors occur because `blis` uses deprecated Python C API functions that were removed or changed in Python 3.13.

## The Solution

### Automatic Resolution (Recommended)

The `setup.sh` script automatically detects Python 3.13 and uses a compatibility-optimized installation process:

1. **Detection**: Checks Python version at runtime
2. **Ordered Installation**: Installs dependencies in a specific order to avoid compilation issues
3. **Prebuilt Wheels**: Uses spaCy's compatible `blis` wheel instead of compiling from source

### Manual Resolution

If you need to install dependencies manually on Python 3.13:

```bash
# 1. Install spaCy first (provides compatible blis wheel)
pip install "spacy>=3.8.0"

# 2. Install misaki dependencies
pip install num2words
pip install misaki

# 3. Install remaining dependencies normally
pip install -r requirements.txt
```

## Technical Details

### Root Cause

- `blis` package fails to compile from source on Python 3.13
- Direct installation of `misaki[en]` triggers `blis` source compilation
- The `[en]` extra pulls in dependencies that require `blis`

### Resolution Strategy

- **spaCy** provides a prebuilt `blis` wheel (version 1.3.0) compatible with Python 3.13
- Installing spaCy first ensures the compatible wheel is used
- Subsequent installations use the existing `blis` instead of compiling from source

### Verified Compatible Versions

- `spacy>=3.8.0` with `blis==1.3.0` (prebuilt wheel)
- `misaki>=0.1.0` with English language support
- `num2words>=0.5.0` (required by misaki[en])

## Benefits of This Approach

1. **No Manual Intervention**: Setup script handles everything automatically
2. **Full Functionality**: All features work including Misaki G2P with English support
3. **Performance**: Uses optimized prebuilt wheels instead of source compilation
4. **Reliability**: Avoids compilation errors and dependency conflicts

## Troubleshooting

### If Installation Still Fails

1. **Clear pip cache**: `pip cache purge`
2. **Use fresh virtual environment**: 
   ```bash
   rm -rf .venv
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. **Run setup script again**: `./setup.sh`

### Manual Verification

Check that Misaki is working correctly:

```bash
python3 -c "from misaki import en; g2p = en.G2P(); print('Success!')"
```

### Fallback Option

If Misaki still fails, the system automatically falls back to `phonemizer-fork`, ensuring TTS functionality is maintained.

## Future Considerations

- Monitor `blis` package updates for native Python 3.13 support
- Update installation order when upstream packages provide compatible wheels
- Consider pinning specific versions if compatibility issues arise

## Related Issues

- [blis Python 3.13 compatibility](https://github.com/explosion/cython-blis/issues)
- [spaCy Python 3.13 support](https://github.com/explosion/spaCy/issues)
- [misaki dependency management](https://github.com/mistralai/misaki/issues) 