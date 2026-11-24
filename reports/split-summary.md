# Split summary — PILOT / NOT FOR RESEARCH

- Protocol: afn-split-v1; release: v1; seed: 42
- Manifest SHA-256: `69ef03be582799d4f5541cadbb85ff2e55e88e3a4d794f6a74d1fdfe8a98786e`
- Groups SHA-256: `3bf9199395a5fb7ba0d063fdebeb40d440e648b379dd28ab8068bcd1474e28fe`
- Grouping audit SHA-256: `88acb1973e8f0ce257b70ffd0439c26f71ab8f894d9cef6f05e8f705cdb1d97b`
- Samples: 352; groups: 342; largest group: 4
- ID coverage and group disjointness: PASS
- Exact text/event and available processed image checks: PASS; missing image files: 286
- Near-duplicate, raw image, publisher and URL relations rely on reviewed grouping mapping.
- Test IDs and audit are QA-only; do not use for tuning. File permissions must be enforced externally.

| Split | Samples | Groups | Actual % | Delta pp | Fake | Real | PF fake | PF real | GC fake | GC real |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| train | 247 | 240 | 70.17 | +0.17 | 131 | 116 | 63 | 49 | 68 | 67 |
| validation | 53 | 51 | 15.06 | +0.06 | 28 | 25 | 13 | 11 | 15 | 14 |
| test | 52 | 51 | 14.77 | -0.23 | 28 | 24 | 13 | 10 | 15 | 14 |

## Split SHA-256
- train.json: `6b8d287512baaeb6875b81547c46354ec14c95c69b2e53054b46ffbc105e9a07`
- validation.json: `0fc195ee6b626bd7e8be61e66a24cb055b4758f8443906aac24ffa0d63fac46b`
- test.json: `3ac3ea182776d545dd84c2b4d1d297e88374f7863abf6582579a1f13db5536d2`

## Blockers and limitations
- No QA grouping approval
- 286 referenced images unavailable; exact image leakage not fully checked

Group integrity takes precedence over exact ratios. No random sample fallback. Changes require a new version; never silently overwrite.
