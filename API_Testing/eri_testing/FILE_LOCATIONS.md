# 📁 File Locations Summary

## Project Directory
**Location**: `C:\Users\Devansh\Desktop\eri_testing\`

---

## 📂 Current Files (10 files)

### ✅ Core Application (3 files)

| File | Type | Size | Purpose |
|------|------|------|---------|
| `CMSTokenSigner.java` | Source | ~10 KB | Main Java signer application |
| `CMSTokenSigner.class` | Compiled | ~8 KB | Compiled Java bytecode |
| `cms_bridge.py` | Python | ~5 KB | Python wrapper for easy use |

**Status**: ✅ All working

---

### 📚 Required Libraries (3 files)

| File | Size | Purpose |
|------|------|---------|
| `bcprov-jdk18on-1.82.jar` | 2.8 MB | BouncyCastle crypto provider |
| `bcpkix-jdk18on-1.82.jar` | 1.2 MB | Certificate/PKIX support |
| `bcutil-jdk18on-1.82.jar` | 0.8 MB | BouncyCastle utilities |

**Total Size**: ~4.8 MB
**Status**: ✅ All required

---

### 📖 Documentation (4 files)

| File | Purpose |
|------|---------|
| `README.md` | Main documentation with file structure |
| `SUCCESS_SUMMARY.md` | Complete success guide & troubleshooting |
| `QUICK_START.md` | Quick reference for daily use |
| `ERI Data Signature process guide V0.2 2 1 1.pdf` | Official ERI specifications |

**Status**: ✅ Complete documentation

---

## 🔐 System Files (External)

### USB Token Driver
**Location**: `C:\Windows\System32\eps2003csp11v2.dll`
- **Type**: 64-bit PKCS#11 driver
- **For**: HYP2003 USB token
- **Status**: ✅ Working

---

## 🗑️ Removed Files (8 files)

These files were removed as they are no longer needed:

| File | Reason for Removal |
|------|-------------------|
| `HyperPKICsp11_2003.dll` | Wrong DLL, not used |
| `HyperPKICsp11_200364.dll` | Wrong DLL, not used |
| `test_token.cmd` | Functionality integrated in main code |
| `check_dll.ps1` | Temporary diagnostic script |
| `check_dll_simple.cmd` | Temporary diagnostic script |
| `download_bc_jars.cmd` | JARs already downloaded |
| `INSTRUCTIONS.md` | Consolidated into README.md |
| `README_CURRENT_STATUS.md` | Consolidated into SUCCESS_SUMMARY.md |

---

## 📊 File Organization

```
eri_testing/
│
├── 🔧 Application Files (Use these)
│   ├── CMSTokenSigner.java      ← Source code
│   ├── CMSTokenSigner.class     ← Compiled (auto-generated)
│   └── cms_bridge.py            ← Python wrapper
│
├── 📦 Libraries (Don't modify)
│   ├── bcprov-jdk18on-1.82.jar
│   ├── bcpkix-jdk18on-1.82.jar
│   └── bcutil-jdk18on-1.82.jar
│
├── 📚 Documentation (Read these)
│   ├── README.md                ← Start here
│   ├── QUICK_START.md           ← Daily reference
│   ├── SUCCESS_SUMMARY.md       ← Complete guide
│   └── FILE_LOCATIONS.md        ← This file
│
└── 📄 Reference
    └── ERI Data Signature process guide V0.2 2 1 1.pdf
```

---

## 🎯 What to Use

### For Daily Use
1. **Quick Test**: See `QUICK_START.md`
2. **Python Integration**: Use `cms_bridge.py`
3. **Java Direct**: Use `CMSTokenSigner.class`

### For Reference
1. **File Structure**: This file (`FILE_LOCATIONS.md`)
2. **Complete Guide**: `SUCCESS_SUMMARY.md`
3. **Project Overview**: `README.md`

### For Development
1. **Source Code**: `CMSTokenSigner.java`
2. **Modify & Recompile**: See README.md
3. **Python Wrapper**: Edit `cms_bridge.py`

---

## 🔄 Backup Recommendation

**Essential Files to Backup**:
```
✅ CMSTokenSigner.java          (source code)
✅ cms_bridge.py                (Python wrapper)
✅ bcprov-jdk18on-1.82.jar     (library)
✅ bcpkix-jdk18on-1.82.jar     (library)
✅ bcutil-jdk18on-1.82.jar     (library)
✅ README.md                    (documentation)
✅ SUCCESS_SUMMARY.md           (documentation)
```

**Can be regenerated**:
- `CMSTokenSigner.class` (compile from .java)
- `QUICK_START.md` (reference only)
- `FILE_LOCATIONS.md` (this file)

---

## 📍 External Dependencies

### System Location
- **USB Token Driver**: `C:\Windows\System32\eps2003csp11v2.dll`
  - Installed by HyperSecu/ePass software
  - Required for token access
  - Do not delete or move

### Java Runtime
- **Location**: System PATH
- **Version**: Java 8+ (tested with Java 25)
- **Check**: `java -version`

### Python (Optional)
- **Location**: System PATH
- **Version**: Python 3.6+
- **Check**: `python --version`

---

## ✅ Verification Checklist

Use this to verify your setup:

- [ ] All 10 files present in `eri_testing` folder
- [ ] 3 BouncyCastle JARs present (total ~4.8 MB)
- [ ] `eps2003csp11v2.dll` exists in `C:\Windows\System32\`
- [ ] USB token inserted
- [ ] Java installed and in PATH
- [ ] Can run: `java -version`
- [ ] Can compile: `javac CMSTokenSigner.java`
- [ ] Can run: `java CMSTokenSigner ...`
- [ ] Python installed (optional)
- [ ] Can run: `python cms_bridge.py`

---

## 🎉 Summary

**Total Files**: 10 files in project folder
**Total Size**: ~5 MB (mostly libraries)
**Status**: ✅ Clean, organized, production-ready

**All unnecessary files removed. Project is ready for use!**

---

*Last Updated: November 13, 2025*
*Status: Production Ready ✅*
