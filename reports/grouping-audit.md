# Grouping audit — PILOT / NOT APPROVED

- Version: `afn-group-v2-pilot`
- Manifest SHA-256: `69ef03be582799d4f5541cadbb85ff2e55e88e3a4d794f6a74d1fdfe8a98786e`
- Mapping SHA-256: `3bf9199395a5fb7ba0d063fdebeb40d440e648b379dd28ab8068bcd1474e28fe`
- Samples: 352; CSV rows: 358; CSV-only IDs: 6
- Groups: 342; largest: 4; singleton groups: 337
- Pair comparisons: 61776
- Coverage, edge consistency and synthetic A–B–C test: PASS.
- No group was split; no labels used for similarity.
- Thresholds are fixed pilot proposals, not calibrated or manually approved. Do not use this mapping for research splits.
- Publisher proxy is normalized URL hostname, not verified corporate ownership. Missing metadata is not treated as a shared key.
- TF-IDF is fitted only for grouping, not exported as a training feature. Event candidates are not verified event IDs.

## Rules

`{"title_candidate": 0.3, "title_only": 0.85, "title_text": 0.72, "text_support": 0.35, "text_near": 0.9, "phash_distance": 4, "title_weight": 0.7}`

NFC/casefold/whitespace normalization; word unigram/bigram TF-IDF cosine; SHA-256 normalized text and image bytes; 64-bit pHash Hamming; URL removes tracking parameters, fragment and www; connected components over all accepted edges.

## Input coverage

| Group | CSV | Manifest |
|---|---:|---:|
| politifact_fake | 91 | 89 |
| politifact_real | 73 | 70 |
| gossipcop_fake | 98 | 98 |
| gossipcop_real | 96 | 95 |

## Missing data

| Field | Count |
|---|---:|
| csv_row | 0 |
| raw_json | 352 |
| url | 352 |
| publisher | 352 |
| event_metadata | 352 |
| title | 0 |
| text | 12 |
| image_absent | 66 |
| processed_image_unreadable | 286 |

## Reconciliation with previous mapping

- Previous groups: 342
- Cross-group exact relations observed: 0
- Remaining observed conflicts: 0
- Missing images prevent complete verification; zero observed conflicts is not proof of zero actual conflicts.

| A | B | Relation | Hash/event |
|---|---|---|---|

## Edge counts

- event_candidate: 8
- previous_group: 10
- text_near: 11
- text_sha256: 7

## Largest groups (review priority)

| Group | Size | Fake | Real |
|---|---:|---:|---:|
| group_0198 | 4 | 1 | 3 |
| group_0206 | 4 | 3 | 1 |
| group_0021 | 3 | 1 | 2 |
| group_0306 | 2 | 0 | 2 |
| group_0318 | 2 | 0 | 2 |
| group_0001 | 1 | 1 | 0 |
| group_0002 | 1 | 1 | 0 |
| group_0003 | 1 | 1 | 0 |
| group_0004 | 1 | 1 | 0 |
| group_0005 | 1 | 1 | 0 |

## Accepted edge evidence (automatic, not human review)

| A | B | Relation | Evidence |
|---|---|---|---|
| gossipcop-3000021440 | gossipcop-925528 | previous_group | group_0021 |
| gossipcop-3000021440 | politifact10945 | previous_group | group_0021 |
| politifact11761 | politifact13132 | previous_group | group_0198 |
| politifact13038 | politifact13515 | previous_group | group_0206 |
| politifact11761 | politifact15383 | previous_group | group_0198 |
| politifact13038 | politifact15573 | previous_group | group_0206 |
| politifact13038 | politifact2019 | previous_group | group_0206 |
| politifact423 | politifact426 | previous_group | group_0318 |
| politifact2298 | politifact681 | previous_group | group_0306 |
| politifact11761 | politifact8838 | previous_group | group_0198 |
| gossipcop-3000021440 | gossipcop-925528 | text_sha256 | 325ac45065a53bb2e3e94731fef0b8e59007d8bf9bd257e2d8f00cf40ba1ac84 |
| gossipcop-3000021440 | politifact10945 | text_sha256 | 325ac45065a53bb2e3e94731fef0b8e59007d8bf9bd257e2d8f00cf40ba1ac84 |
| politifact11761 | politifact13132 | text_sha256 | 9bd1d2f66a3e6f8dc5342a3db7d1ecb54b96b59293b293b00e2a24b2de02c15e |
| politifact11761 | politifact15383 | text_sha256 | 9bd1d2f66a3e6f8dc5342a3db7d1ecb54b96b59293b293b00e2a24b2de02c15e |
| politifact423 | politifact426 | text_sha256 | 6cc0e10b436d1e5040d23a07a25ee14629ac6e01e430c51a387528b0fea90b9a |
| politifact2298 | politifact681 | text_sha256 | 25f8619f9c543d7847b4d3aa39a8dd7e7f9ad3ed7361b37fc63d05b2f1a67028 |
| politifact11761 | politifact8838 | text_sha256 | 9bd1d2f66a3e6f8dc5342a3db7d1ecb54b96b59293b293b00e2a24b2de02c15e |
| gossipcop-3000021440 | gossipcop-925528 | text_near | 1.0000 |
| gossipcop-3000021440 | politifact10945 | text_near | 1.0000 |
| gossipcop-925528 | politifact10945 | text_near | 1.0000 |
| politifact11761 | politifact13132 | text_near | 1.0000 |
| politifact11761 | politifact15383 | text_near | 1.0000 |
| politifact11761 | politifact8838 | text_near | 1.0000 |
| politifact13038 | politifact13515 | event_candidate | title=1.0000; text missing |
| politifact13038 | politifact15573 | event_candidate | title=1.0000; text missing |
| politifact13038 | politifact2019 | event_candidate | title=1.0000; text missing |
| politifact13132 | politifact15383 | text_near | 1.0000 |
| politifact13132 | politifact8838 | text_near | 1.0000 |
| politifact13515 | politifact15573 | event_candidate | title=1.0000; text missing |
| politifact13515 | politifact2019 | event_candidate | title=1.0000; text missing |
| politifact15383 | politifact8838 | text_near | 1.0000 |
| politifact15573 | politifact2019 | event_candidate | title=1.0000; text missing |
| politifact2298 | politifact681 | text_near | 1.0000 |
| politifact2298 | politifact681 | event_candidate | title=1.0000; text=1.0000 |
| politifact423 | politifact426 | text_near | 1.0000 |
| politifact423 | politifact426 | event_candidate | title=1.0000; text=1.0000 |

## Event candidates for manual review

| A | B | Title cosine | Text cosine | Score | Accepted |
|---|---|---:|---:|---:|---|
| politifact423 | politifact426 | 1.0000 | 1.0000000000000246 | 1.0000 | True |
| politifact13038 | politifact13515 | 1.0000 | NA | 1.0000 | True |
| politifact13038 | politifact15573 | 1.0000 | NA | 1.0000 | True |
| politifact13038 | politifact2019 | 1.0000 | NA | 1.0000 | True |
| politifact13515 | politifact15573 | 1.0000 | NA | 1.0000 | True |
| politifact13515 | politifact2019 | 1.0000 | NA | 1.0000 | True |
| politifact15573 | politifact2019 | 1.0000 | NA | 1.0000 | True |
| politifact2298 | politifact681 | 1.0000 | 0.9999999999999996 | 1.0000 | True |
| politifact246 | politifact5321 | 1.0000 | 0.12954042088599602 | 0.7389 | False |
| gossipcop-930832 | gossipcop-9521617242 | 0.5711 | 0.10202848985800403 | 0.4304 | False |
| gossipcop-9067502868 | gossipcop-9878194459 | 0.4721 | 0.1098192388274776 | 0.3634 | False |
| gossipcop-7105802899 | gossipcop-8877042466 | 0.4229 | 0.13911247082524272 | 0.3378 | False |
| gossipcop-5476631226 | gossipcop-907816 | 0.3828 | 0.1825806647304823 | 0.3227 | False |
| gossipcop-855860 | gossipcop-897431 | 0.4328 | 0.058086028270394954 | 0.3204 | False |
| gossipcop-5663483713 | gossipcop-889953 | 0.3642 | 0.21618633118496902 | 0.3198 | False |
| gossipcop-7105802899 | gossipcop-938852 | 0.3912 | 0.08571469631912557 | 0.2995 | False |
| gossipcop-4492802133 | gossipcop-976889623 | 0.3836 | 0.10117212411859344 | 0.2989 | False |
| gossipcop-2485085069 | gossipcop-610873029 | 0.3916 | 0.058400177544265464 | 0.2917 | False |
| politifact1825 | politifact2093 | 0.3692 | 0.07009926580380624 | 0.2795 | False |
| politifact2093 | politifact2166 | 0.3764 | 0.05039144405591073 | 0.2786 | False |
| politifact1783 | politifact2093 | 0.3692 | 0.057610971532922606 | 0.2757 | False |
| gossipcop-1914781905 | gossipcop-930658 | 0.3431 | 0.10740633842047077 | 0.2724 | False |
| gossipcop-2875496174 | gossipcop-7105802899 | 0.3419 | 0.11013067112156985 | 0.2724 | False |
| gossipcop-8877042466 | gossipcop-938852 | 0.3273 | 0.14168616578199122 | 0.2716 | False |
| gossipcop-6747642549 | gossipcop-860866 | 0.3513 | 0.04560873456931187 | 0.2596 | False |
| gossipcop-2405182303 | gossipcop-9067502868 | 0.3210 | 0.08905033823586157 | 0.2514 | False |
| gossipcop-6183599706 | gossipcop-924603 | 0.3078 | 0.0979970479625944 | 0.2449 | False |
| gossipcop-931132 | gossipcop-9454452528 | 0.3119 | 0.066550378034178 | 0.2383 | False |
| politifact2093 | politifact3693 | 0.3286 | 0.02210065749758106 | 0.2367 | False |
| gossipcop-5476631226 | gossipcop-9521617242 | 0.3169 | 0.03936126213797668 | 0.2336 | False |
| gossipcop-848179 | gossipcop-850436 | 0.3111 | 0.02638297711647778 | 0.2257 | False |

## Member table

| Sample ID | Group ID |
|---|---|
| gossipcop-1020335052 | group_0001 |
| gossipcop-1026793571 | group_0002 |
| gossipcop-1032664975 | group_0003 |
| gossipcop-1225099614 | group_0004 |
| gossipcop-1537399397 | group_0005 |
| gossipcop-1606507932 | group_0006 |
| gossipcop-1914781905 | group_0007 |
| gossipcop-2076682877 | group_0008 |
| gossipcop-2182023698 | group_0009 |
| gossipcop-2210288941 | group_0010 |
| gossipcop-22281334 | group_0011 |
| gossipcop-2279820101 | group_0012 |
| gossipcop-2345398796 | group_0013 |
| gossipcop-2365780434 | group_0014 |
| gossipcop-2405182303 | group_0015 |
| gossipcop-2485085069 | group_0016 |
| gossipcop-2547891536 | group_0017 |
| gossipcop-2552051738 | group_0018 |
| gossipcop-2803748870 | group_0019 |
| gossipcop-2875496174 | group_0020 |
| gossipcop-3000021440 | group_0021 |
| gossipcop-3084428038 | group_0022 |
| gossipcop-3175262640 | group_0023 |
| gossipcop-3196321022 | group_0024 |
| gossipcop-324494433 | group_0025 |
| gossipcop-3448636303 | group_0026 |
| gossipcop-3449648617 | group_0027 |
| gossipcop-3503563094 | group_0028 |
| gossipcop-3795940197 | group_0029 |
| gossipcop-3896029098 | group_0030 |
| gossipcop-392859545 | group_0031 |
| gossipcop-3976443648 | group_0032 |
| gossipcop-3996753978 | group_0033 |
| gossipcop-4209182367 | group_0034 |
| gossipcop-4258497840 | group_0035 |
| gossipcop-4308581568 | group_0036 |
| gossipcop-4373322193 | group_0037 |
| gossipcop-4433782210 | group_0038 |
| gossipcop-4492802133 | group_0039 |
| gossipcop-4924282374 | group_0040 |
| gossipcop-4963306668 | group_0041 |
| gossipcop-5009074529 | group_0042 |
| gossipcop-5035404255 | group_0043 |
| gossipcop-5051410001 | group_0044 |
| gossipcop-5061123187 | group_0045 |
| gossipcop-5189580095 | group_0046 |
| gossipcop-5288672998 | group_0047 |
| gossipcop-5328443100 | group_0048 |
| gossipcop-5476631226 | group_0049 |
| gossipcop-5493993751 | group_0050 |
| gossipcop-5663483713 | group_0051 |
| gossipcop-5671352259 | group_0052 |
| gossipcop-6010530745 | group_0053 |
| gossipcop-6068765070 | group_0054 |
| gossipcop-610873029 | group_0055 |
| gossipcop-6183599706 | group_0056 |
| gossipcop-6504249629 | group_0057 |
| gossipcop-6747642549 | group_0058 |
| gossipcop-6751025589 | group_0059 |
| gossipcop-6793729315 | group_0060 |
| gossipcop-687368041 | group_0061 |
| gossipcop-7010349230 | group_0062 |
| gossipcop-7105802899 | group_0063 |
| gossipcop-7147482030 | group_0064 |
| gossipcop-7391946984 | group_0065 |
| gossipcop-7499447250 | group_0066 |
| gossipcop-7894516039 | group_0067 |
| gossipcop-8105333868 | group_0068 |
| gossipcop-8107039710 | group_0069 |
| gossipcop-8183298967 | group_0070 |
| gossipcop-8192653419 | group_0071 |
| gossipcop-829660617 | group_0072 |
| gossipcop-8347611424 | group_0073 |
| gossipcop-845913 | group_0074 |
| gossipcop-846137 | group_0075 |
| gossipcop-846305 | group_0076 |
| gossipcop-848179 | group_0077 |
| gossipcop-848402 | group_0078 |
| gossipcop-850409 | group_0079 |
| gossipcop-850436 | group_0080 |
| gossipcop-850948 | group_0081 |
| gossipcop-855860 | group_0082 |
| gossipcop-856576 | group_0083 |
| gossipcop-857248 | group_0084 |
| gossipcop-857434 | group_0085 |
| gossipcop-860726 | group_0086 |
| gossipcop-860866 | group_0087 |
| gossipcop-8611166284 | group_0088 |
| gossipcop-863169 | group_0089 |
| gossipcop-863614 | group_0090 |
| gossipcop-864237 | group_0091 |
| gossipcop-864634 | group_0092 |
| gossipcop-866366 | group_0093 |
| gossipcop-867108 | group_0094 |
| gossipcop-868602 | group_0095 |
| gossipcop-868642 | group_0096 |
| gossipcop-870571 | group_0097 |
| gossipcop-872759 | group_0098 |
| gossipcop-873029 | group_0099 |
| gossipcop-873033733 | group_0100 |
| gossipcop-8750519313 | group_0101 |
| gossipcop-8753274298 | group_0102 |
| gossipcop-875924 | group_0103 |
| gossipcop-877019 | group_0104 |
| gossipcop-878391 | group_0105 |
| gossipcop-881302 | group_0106 |
| gossipcop-881554 | group_0107 |
| gossipcop-882128 | group_0108 |
| gossipcop-882656 | group_0109 |
| gossipcop-884026 | group_0110 |
| gossipcop-884442 | group_0111 |
| gossipcop-884684 | group_0112 |
| gossipcop-8871505752 | group_0113 |
| gossipcop-887233 | group_0114 |
| gossipcop-8877042466 | group_0115 |
| gossipcop-889739 | group_0116 |
| gossipcop-889953 | group_0117 |
| gossipcop-890124 | group_0118 |
| gossipcop-890284 | group_0119 |
| gossipcop-890423 | group_0120 |
| gossipcop-893257 | group_0121 |
| gossipcop-894416 | group_0122 |
| gossipcop-896255 | group_0123 |
| gossipcop-896517 | group_0124 |
| gossipcop-896961 | group_0125 |
| gossipcop-897431 | group_0126 |
| gossipcop-897603 | group_0127 |
| gossipcop-898585 | group_0128 |
| gossipcop-899337 | group_0129 |
| gossipcop-8996311550 | group_0130 |
| gossipcop-899874 | group_0131 |
| gossipcop-900065 | group_0132 |
| gossipcop-901312 | group_0133 |
| gossipcop-905887 | group_0134 |
| gossipcop-9067502868 | group_0135 |
| gossipcop-906795 | group_0136 |
| gossipcop-907231 | group_0137 |
| gossipcop-907647 | group_0138 |
| gossipcop-907816 | group_0139 |
| gossipcop-908089 | group_0140 |
| gossipcop-908254 | group_0141 |
| gossipcop-908402 | group_0142 |
| gossipcop-908630 | group_0143 |
| gossipcop-9093067371 | group_0144 |
| gossipcop-9098202484 | group_0145 |
| gossipcop-912950 | group_0146 |
| gossipcop-914742 | group_0147 |
| gossipcop-915349 | group_0148 |
| gossipcop-917421 | group_0149 |
| gossipcop-918831 | group_0150 |
| gossipcop-918922 | group_0151 |
| gossipcop-921146 | group_0152 |
| gossipcop-9212719071 | group_0153 |
| gossipcop-923759 | group_0154 |
| gossipcop-924603 | group_0155 |
| gossipcop-925528 | group_0021 |
| gossipcop-926957 | group_0156 |
| gossipcop-929920 | group_0157 |
| gossipcop-930203 | group_0158 |
| gossipcop-930658 | group_0159 |
| gossipcop-930832 | group_0160 |
| gossipcop-931132 | group_0161 |
| gossipcop-931325 | group_0162 |
| gossipcop-933029 | group_0163 |
| gossipcop-935087 | group_0164 |
| gossipcop-936100 | group_0165 |
| gossipcop-9368279509 | group_0166 |
| gossipcop-938852 | group_0167 |
| gossipcop-939148 | group_0168 |
| gossipcop-939721 | group_0169 |
| gossipcop-940180 | group_0170 |
| gossipcop-941294 | group_0171 |
| gossipcop-941805037 | group_0172 |
| gossipcop-941864 | group_0173 |
| gossipcop-9444654745 | group_0174 |
| gossipcop-9454452528 | group_0175 |
| gossipcop-947934 | group_0176 |
| gossipcop-949910 | group_0177 |
| gossipcop-9503284683 | group_0178 |
| gossipcop-950749 | group_0179 |
| gossipcop-950782 | group_0180 |
| gossipcop-9521617242 | group_0181 |
| gossipcop-952953 | group_0182 |
| gossipcop-953107 | group_0183 |
| gossipcop-955009 | group_0184 |
| gossipcop-9636141965 | group_0185 |
| gossipcop-9650269391 | group_0186 |
| gossipcop-9658632569 | group_0187 |
| gossipcop-9752823264 | group_0188 |
| gossipcop-976889623 | group_0189 |
| gossipcop-9878194459 | group_0190 |
| gossipcop-988336091 | group_0191 |
| gossipcop-9940338306 | group_0192 |
| politifact10787 | group_0193 |
| politifact1084 | group_0194 |
| politifact10945 | group_0021 |
| politifact11580 | group_0195 |
| politifact11711 | group_0196 |
| politifact11747 | group_0197 |
| politifact11761 | group_0198 |
| politifact118 | group_0199 |
| politifact11899 | group_0200 |
| politifact11960 | group_0201 |
| politifact11989 | group_0202 |
| politifact1202 | group_0203 |
| politifact12148 | group_0204 |
| politifact12773 | group_0205 |
| politifact13038 | group_0206 |
| politifact13132 | group_0198 |
| politifact13193 | group_0207 |
| politifact13303 | group_0208 |
| politifact13467 | group_0209 |
| politifact13484 | group_0210 |
| politifact13515 | group_0206 |
| politifact13557 | group_0211 |
| politifact13559 | group_0212 |
| politifact13565 | group_0213 |
| politifact13570 | group_0214 |
| politifact13589 | group_0215 |
| politifact13745 | group_0216 |
| politifact13765 | group_0217 |
| politifact13773 | group_0218 |
| politifact13775 | group_0219 |
| politifact13794 | group_0220 |
| politifact13806 | group_0221 |
| politifact13827 | group_0222 |
| politifact13836 | group_0223 |
| politifact13854 | group_0224 |
| politifact13887 | group_0225 |
| politifact13897 | group_0226 |
| politifact13924 | group_0227 |
| politifact13982 | group_0228 |
| politifact13999 | group_0229 |
| politifact14005 | group_0230 |
| politifact14008 | group_0231 |
| politifact14051 | group_0232 |
| politifact14064 | group_0233 |
| politifact14071 | group_0234 |
| politifact14123 | group_0235 |
| politifact14211 | group_0236 |
| politifact14222 | group_0237 |
| politifact14233 | group_0238 |
| politifact14235 | group_0239 |
| politifact14236 | group_0240 |
| politifact14238 | group_0241 |
| politifact14243 | group_0242 |
| politifact14278 | group_0243 |
| politifact14297 | group_0244 |
| politifact14327 | group_0245 |
| politifact14328 | group_0246 |
| politifact14356 | group_0247 |
| politifact14384 | group_0248 |
| politifact14386 | group_0249 |
| politifact14394 | group_0250 |
| politifact14426 | group_0251 |
| politifact14454 | group_0252 |
| politifact14469 | group_0253 |
| politifact14472 | group_0254 |
| politifact14474 | group_0255 |
| politifact14514 | group_0256 |
| politifact14543 | group_0257 |
| politifact14548 | group_0258 |
| politifact14564 | group_0259 |
| politifact14565 | group_0260 |
| politifact14567 | group_0261 |
| politifact14596 | group_0262 |
| politifact14621 | group_0263 |
| politifact14624 | group_0264 |
| politifact14693 | group_0265 |
| politifact14698 | group_0266 |
| politifact14742 | group_0267 |
| politifact14745 | group_0268 |
| politifact14759 | group_0269 |
| politifact14795 | group_0270 |
| politifact14950 | group_0271 |
| politifact14954 | group_0272 |
| politifact14984 | group_0273 |
| politifact15096 | group_0274 |
| politifact15097 | group_0275 |
| politifact15130 | group_0276 |
| politifact15138 | group_0277 |
| politifact15158 | group_0278 |
| politifact15159 | group_0279 |
| politifact15164 | group_0280 |
| politifact15205 | group_0281 |
| politifact15210 | group_0282 |
| politifact15251 | group_0283 |
| politifact15262 | group_0284 |
| politifact15263 | group_0285 |
| politifact15267 | group_0286 |
| politifact15291 | group_0287 |
| politifact15309 | group_0288 |
| politifact15355 | group_0289 |
| politifact15362 | group_0290 |
| politifact15367 | group_0291 |
| politifact15383 | group_0198 |
| politifact15482 | group_0292 |
| politifact15486 | group_0293 |
| politifact15501 | group_0294 |
| politifact15525 | group_0295 |
| politifact15573 | group_0206 |
| politifact15625 | group_0296 |
| politifact1755 | group_0297 |
| politifact1770 | group_0298 |
| politifact1783 | group_0299 |
| politifact1825 | group_0300 |
| politifact20 | group_0301 |
| politifact2013 | group_0302 |
| politifact2019 | group_0206 |
| politifact206 | group_0303 |
| politifact2093 | group_0304 |
| politifact2166 | group_0305 |
| politifact2298 | group_0306 |
| politifact246 | group_0307 |
| politifact3180 | group_0308 |
| politifact333 | group_0309 |
| politifact3335 | group_0310 |
| politifact3527 | group_0311 |
| politifact3693 | group_0312 |
| politifact374 | group_0313 |
| politifact384 | group_0314 |
| politifact3892 | group_0315 |
| politifact401 | group_0316 |
| politifact4181 | group_0317 |
| politifact423 | group_0318 |
| politifact426 | group_0318 |
| politifact4275 | group_0319 |
| politifact442 | group_0320 |
| politifact4809 | group_0321 |
| politifact4887 | group_0322 |
| politifact4926 | group_0323 |
| politifact51 | group_0324 |
| politifact514 | group_0325 |
| politifact5321 | group_0326 |
| politifact537 | group_0327 |
| politifact548 | group_0328 |
| politifact5632 | group_0329 |
| politifact66 | group_0330 |
| politifact6641 | group_0331 |
| politifact667 | group_0332 |
| politifact681 | group_0306 |
| politifact690 | group_0333 |
| politifact746 | group_0334 |
| politifact769 | group_0335 |
| politifact779 | group_0336 |
| politifact785 | group_0337 |
| politifact7888 | group_0338 |
| politifact8069 | group_0339 |
| politifact8085 | group_0340 |
| politifact8838 | group_0198 |
| politifact9691 | group_0341 |
| politifact9734 | group_0342 |

## Release blockers

Review accepted/rejected event candidates, cross-label exact text, publisher aliases and large components. Re-run with accessible raw JSON and processed images; record human approval and freeze rules before official split. A missing event relation cannot be ruled out by low lexical similarity.
