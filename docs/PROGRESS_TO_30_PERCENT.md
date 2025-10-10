# Progress to 30% Coverage - Final Push

**Date:** 2025-10-09  
**Current:** 25%  
**Target:** 30%  
**Gap:** 5 percentage points  
**Status:** 🎯 Final push for Week 1 goal

---

## Current State

### Overall Metrics

| Metric | Value |
|--------|-------|
| **Current Coverage** | 25% |
| **Target Coverage** | 30% |
| **Gap** | 5 pp |
| **Statements Needed** | ~472 more statements |
| **Total Tests** | 268 |
| **Passing Tests** | 198 (74%) |

### Modules Tested So Far

| Module | Coverage | Tests | Status |
|--------|----------|-------|--------|
| api/tts/core.py | 53% | 84 | ✅ Excellent |
| api/model/providers/coreml.py | 55% | 37 | ✅ Excellent |
| api/model/providers/ort.py | ~70% | 32 | ✅ Excellent |
| api/model/sessions/manager.py | 48% | 24 | ✅ Good |
| api/config.py | 43% | 12 | 🟡 Existing |
| api/warnings.py | 50% | 0 | 🟡 Incidental |

---

## Strategy to Reach 30%

### Options Analysis

**Option 1: Test Large 0% Module (Best ROI)**
- Target: `api/performance/optimization.py` (484 statements, 13%)
- Goal: 13% → 40% (+27 pp) = ~130 statements
- Tests needed: 25-30
- Time: 2 hours
- Coverage gain: ~1.4%

**Option 2: Test Medium 0% Module**
- Target: `api/performance/stats.py` (347 statements, 24%)
- Goal: 24% → 50% (+26 pp) = ~90 statements
- Tests needed: 20-25
- Time: 1.5 hours
- Coverage gain: ~1%

**Option 3: Test Multiple Small Modules**
- Targets: Several small 0% modules
- Combined statements: ~500
- Tests needed: 40-50
- Time: 2-3 hours
- Coverage gain: ~5%

**Option 4: Expand Existing Tests**
- Improve coverage on partially tested modules
- Add edge cases and error paths
- Tests needed: 30-40
- Time: 2 hours
- Coverage gain: ~2-3%

---

## Recommended Approach

### Quick Wins Strategy (2-3 Hours to 30%)

**Target Bundle:**
1. Expand `api/config.py` tests (43% → 65%) = +49 statements = +0.5%
2. Test `api/model/loader.py` (80% → 100%) = +8 statements = +0.08%
3. Test `api/performance/stats.py` (24% → 45%) = +73 statements = +0.77%
4. Test `api/routes/performance.py` (21% → 40%) = +38 statements = +0.4%
5. Test `api/performance/request_tracker.py` (55% → 75%) = +21 statements = +0.22%

**Total Expected:** ~189 statements = ~2% gain

**Then for remaining +3%:**
6. Test `api/performance/ttfa_monitor.py` (0% → 40%) = +70 statements = +0.74%
7. Test `api/model/hardware/capabilities.py` (29% → 60%) = +7 statements = +0.07%
8. Test `api/utils/temp_management.py` (41% → 70%) = +19 statements = +0.2%
9. Test additional functions in already-tested modules = +195 statements = +2%

**Total:** ~472 statements = +5% to reach 30%

---

## Immediate Action Plan

### Session 4: Push to 30%

**Hour 1: Config & Utils Expansion**
- Expand `api/config.py` tests
- Test `api/model/loader.py`
- Test `api/utils/temp_management.py`
- Expected: +1% coverage

**Hour 2: Performance Modules**
- Test `api/performance/stats.py`
- Test `api/performance/request_tracker.py`
- Expected: +1% coverage

**Hour 3: TTFA Monitor & Cleanup**
- Test `api/performance/ttfa_monitor.py`
- Test `api/routes/performance.py`
- Expected: +1.5% coverage

**Hour 4: Final Push**
- Add more tests to best-performing modules
- Fix any remaining easy failures
- Expected: +1.5% coverage

**Total:** 30%+ coverage achieved ✅

---

## Tests to Create

### Estimated Test Count

| Module | Current Tests | Need to Add | Total |
|--------|---------------|-------------|-------|
| api/config.py | 12 | +15 | 27 |
| api/model/loader.py | 0 | +10 | 10 |
| api/performance/stats.py | 0 | +20 | 20 |
| api/performance/request_tracker.py | 0 | +15 | 15 |
| api/performance/ttfa_monitor.py | 0 | +18 | 18 |
| api/routes/performance.py | 0 | +15 | 15 |
| api/utils/temp_management.py | 0 | +12 | 12 |
| **Total** | **12** | **+105** | **117** |

**Grand Total Tests:** 268 + 105 = 373 tests

---

## Timeline

**Current Time:** End of Session 4  
**To 30%:** 3-4 more hours  
**ETA:** End of current session or next session

---

## Success Criteria

- [x] 25% coverage achieved
- [ ] 30% coverage achieved
- [ ] Week 1 goal met
- [ ] 100+ new tests in this push
- [ ] All critical modules >40% coverage

---

**Status:** Ready for final push to 30%  
**Confidence:** High  
**Next:** Config expansion then performance modules

