"""Production overlap-guard regression and CSV replay without GUI imports.

CLI: python -B test/helpers/wand_radius_experiment.py --inputs A.csv B.csv
     --output .opencode/outputs/wand_main_fingerprint_repair/report.json
Filtered rows are comparison references, not physical truth or extra candidates.
"""
import argparse
import ast
from collections import Counter
import contextlib
import copy
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'modules/camera_calibration/wand_calibration/wand_calibrator.py'
# Verified main 703b07a + unchanged guard. Normalize newline encoding only:
# unrelated main additions track 3D point/frame IDs; peak/generator ASTs match
# review/pr-24 and HEAD (see repair provenance). Arbitrary module drift fails.
SOURCE_SHA256 = 'a9f028b9be03d92852498f9de6cd69ae0327588fbc0cf32f1a45221ea9bbee49'
LEGACY_SOURCE_SHA256 = '765403aee37db96d8b62631b9c5c73b98727e57ea1eb515ee7ed274f11a72dea'
# Captured before integration; location-independent AST, not a self-derived baseline.
LEGACY_PEAK_AST_SHA256 = '97c1b9e1ecb9201fa7e2495df251efa57fb589031eceb5acaba4ccfc744e6ff9'
INTEGRATED_PEAK_AST_SHA256 = '415919bb0a80cd292a17a382b7659cbf954f7c0cd97135689aebeee215cca01a'
LEGACY_GENERATOR_AST_SHA256 = 'b484514516cdedda69a2625f22d7c898f45019b8752ccb19f48999aec7e37e58'
GUARD_SOURCE = '''support_overlap = max(range_s[0], range_l[0]) <= min(range_s[1], range_l[1])
shared_members = sum(range_s[0] <= x <= range_s[1] and range_l[0] <= x <= range_l[1] for x in radii)
if support_overlap or shared_members > 0:
    print(f"Cam {cam_idx}: Discarding peak stats: Small/Large supports overlap "
          f"(S[{range_s[0]:.1f}, {range_s[1]:.1f}], L[{range_l[0]:.1f}, {range_l[1]:.1f}], "
          f"shared samples={shared_members}).")
    return None
'''


def digest(path):
    """Return the SHA256 of path's exact bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalized_source_digest():
    """Return the current module's UTF-8 hash after universal-newline decoding."""
    return hashlib.sha256(SOURCE.read_text(encoding='utf-8').encode('utf-8')).hexdigest()


def production_peak():
    """Compile the actual production peak method without AST edits or GUI imports."""
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'WandCalibrator')
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_filter_radius_histogram_peaks')
    ns = {'np': np}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(SOURCE), 'exec'), ns)
    return ns[node.name]


def ast_digest(node):
    """Return a location-independent AST fingerprint."""
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


def extract():
    """Return genuine legacy peak, ACTUAL production peak, observed generator tail.

    Legacy removes exactly the unique, structurally checked three-node guard.
    Its AST must match the pre-integration fingerprint. Production is compiled
    WITHOUT observations/guard insertion. Generator fingerprint must also match
    pre-integration source; only pass1/final observation assignments are added.
    """
    assert normalized_source_digest() == SOURCE_SHA256, 'Source drift: review/rebind experiment before use'
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'WandCalibrator')
    def method(name):
        return copy.deepcopy(next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name))
    def compile_node(node):
        ns = {'np': np}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                     str(SOURCE) + ':test_AST', 'exec'), ns)
        return ns[node.name]
    def assignment(node, name):
        return isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
    peak = method('_filter_radius_histogram_peaks')
    assert ast_digest(peak) == INTEGRATED_PEAK_AST_SHA256, 'Integrated peak method changed'
    legacy = copy.deepcopy(peak)
    at = next(i for i, n in enumerate(legacy.body) if assignment(n, 'data_l')) + 1
    guard = ast.parse(GUARD_SOURCE).body
    assert len(guard) == 3
    assert [ast.dump(n) for n in legacy.body[at:at+3]] == [ast.dump(n) for n in guard], 'Guard changed/missing: review baseline reconstruction'
    assert sum(assignment(n, 'support_overlap') for n in legacy.body) == 1, 'Guard must occur exactly once'
    del legacy.body[at:at+3]
    assert ast_digest(legacy) == LEGACY_PEAK_AST_SHA256, 'Reconstructed legacy is not the original method'
    gen = method('detect_wand_points_generator')
    assert ast_digest(gen) == LEGACY_GENERATOR_AST_SHA256, 'Selection/fallback/refinement changed'
    start = next(i for i, n in enumerate(gen.body) if assignment(n, 'cam_stats'))
    tail = ast.parse('def replay(self, cam_indices, num_frames, autosave_path=None):\n    pass').body[0]
    tail.body = copy.deepcopy(gen.body[start:])
    refinement = next(i for i, n in enumerate(tail.body) if isinstance(n, ast.If)
                      and ast.unparse(n.test) == 'len(self.wand_data_filtered) > 100')
    tail.body[refinement:refinement] = ast.parse('''self._pass1_stats = cam_stats
self._pass1_pairs = {f: dict(v) for f, v in self.wand_data_filtered.items()}''').body
    tail.body.extend(ast.parse("self._final_stats = locals().get('cam_stats_refined', cam_stats)").body)
    assert not any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in ast.walk(tail))
    return compile_node(legacy), compile_node(peak), compile_node(tail)


def run(raw, cams, peak, replay):
    """Execute source filtering on raw objects; return state/diagnostics/log."""
    obj = SimpleNamespace(wand_data_raw=raw, wand_data_filtered={}, wand_points={},
                          _pass1_stats={}, _pass1_pairs={}, _final_stats={})
    diagnostics = {}
    def wrapped(radii, cam):
        peak_log = io.StringIO()
        with contextlib.redirect_stdout(peak_log):
            result = peak(obj, radii, cam)
        print(peak_log.getvalue(), end='')
        diagnostics[cam] = dict(peak_result=result, fallback_used=result is None,
                                overlap_guard_rejected='Discarding peak stats' in peak_log.getvalue())
        return result
    obj._filter_radius_histogram_peaks = wrapped
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        replay(obj, cams, len(raw))
    return obj, diagnostics, log.getvalue()


def load_csv(path):
    """Inventory all rows; preserve raw identities and separate reference labels."""
    raw, provenance, reference = {}, {}, {}
    statuses, missing, nonfinite, duplicates = Counter(), Counter(), Counter(), Counter()
    groups = {}
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        header, rows = reader.fieldnames, list(reader)
    required = ['Frame', 'Camera', 'Status', 'PointIdx', 'X', 'Y', 'Radius', 'Metric']
    if header != required:
        raise ValueError(f'Incompatible schema: {header}; expected {required}')
    for line, row in enumerate(rows, 2):
        for k in required:
            if row.get(k) in (None, ''):
                missing[k] += 1
        if any(row.get(k) in (None, '') for k in required):
            continue
        f, c, idx = (int(row[k]) for k in ('Frame', 'Camera', 'PointIdx'))
        status = row['Status']
        statuses[status] += 1
        duplicates[(f, c, status, idx)] += 1
        pt = [float(row[k]) for k in ('X', 'Y', 'Radius', 'Metric')]
        for k, v in zip(required[4:], pt):
            if not np.isfinite(v):
                nonfinite[k] += 1
        groups.setdefault(status, {}).setdefault((f, c), []).append(pt)
        if status == 'Raw':
            raw.setdefault(f, {}).setdefault(c, []).append(pt)
            provenance[id(pt)] = [line, f, c, idx, *pt]
        elif status in ('Filtered_Small', 'Filtered_Large'):
            reference.setdefault((f, c), {})[status] = pt
    inventories = {}
    for status, cells in groups.items():
        fs, cs = sorted({f for f, c in cells}), sorted({c for f, c in cells})
        inventories[status] = dict(frames=len(fs), cameras=cs, frame_min=min(fs), frame_max=max(fs),
                                  missing_frame_ids=sorted(set(range(min(fs), max(fs)+1)) - set(fs)),
                                  missing_camera_cells=len(fs)*len(cs)-len(cells),
                                  points_per_camera_frame=dict(Counter(map(len, cells.values()))))
    inventory = dict(header=header, rows=len(rows), statuses=dict(statuses), by_status=inventories,
                     missing_fields=dict(missing), nonfinite_fields=dict(nonfinite),
                     duplicate_keys=sum(n-1 for n in duplicates.values()),
                     incomplete_reference_groups=sum(len(v) != 2 for v in reference.values()))
    inventory['unsafe'] = bool(missing or nonfinite or inventory['duplicate_keys'])
    return raw, provenance, reference, inventory


def decision(pts, stats):
    """Independent audit of source strict candidate/metric selection, not truth."""
    if pts is None:
        return 'missing_camera', None
    if stats is None:
        return 'missing_stats', None
    choices = [[p for p in pts if abs(p[2]-stats[k][0]) < max(3*stats[k][1], .05*stats[k][0])]
               for k in ('s', 'l')]
    if not choices[0] or not choices[1]:
        return 'no_small_and_large' if not any(choices) else 'no_small' if not choices[0] else 'no_large', None
    s = max(choices[0], key=lambda p: p[3])
    large = [p for p in choices[1] if p[:2] != s[:2]]
    return ('accepted', [s, max(large, key=lambda p: p[3])]) if large else ('no_distinct_large', None)


def summarize(raw, provenance, cams, stats, pairs):
    """Audit count/identity/XY invariants and record (not hide) reversed radii."""
    counts, first, reconstructed = {c: Counter() for c in cams}, Counter(), {}
    reversed_pairs = []
    for f, data in raw.items():
        results = {c: decision(data.get(c), stats.get(c)) for c in cams}
        for c, (reason, pair) in results.items():
            counts[c][reason] += 1
            if pair and pair[0][2] >= pair[1][2]:
                reversed_pairs.append([f, c])
        reason = next((f'camera_{c}:{results[c][0]}' for c in cams if results[c][0] != 'accepted'), 'accepted')
        first[reason] += 1
        if reason == 'accepted':
            reconstructed[f] = {c: results[c][1] for c in cams}
    assert set(reconstructed) == set(pairs)
    identities = {}
    for f, data in pairs.items():
        assert set(data) == set(cams)
        for c, pair in data.items():
            assert all(a is b for a, b in zip(pair, reconstructed[f][c]))
            assert pair[0] is not pair[1] and pair[0][:2] != pair[1][:2]
            for p in pair:
                record = provenance[id(p)]
                assert record[1:3] == [f, c] and record[4:] == p
            identities[f'{f}:{c}'] = [provenance[id(p)] for p in pair]
    return dict(valid_frames=len(pairs), filtered_rows=2*len(cams)*len(pairs),
                per_camera_decisions=counts, global_first_rejection=first,
                local_nonincreasing_radius_pairs=reversed_pairs, selected_identities=identities,
                invariant_checks=dict(global_frame_keys_matched=True, selected_original_objects=True,
                                      frame_camera_xy_values_unchanged=True, distinct_objects_and_xy=True,
                                      selected_pairs_checked=len(identities)))


def compare(a, b):
    """Compare ordered row identities on common frames, plus gained/lost keys."""
    common = sorted(set(a) & set(b))
    return dict(common_camera_frames=len(common), changed_camera_frames=[k for k in common if a[k] != b[k]],
                only_left=sorted(set(a)-set(b)), only_right=sorted(set(b)-set(a)))


def replay_csv(path, functions):
    """Return production-vs-legacy replay with hashes and reference comparisons."""
    before = digest(path)
    raw, provenance, reference, inventory = load_csv(path)
    report = dict(input=str(path), sha256_before=before, inventory=inventory)
    if inventory['unsafe'] or not raw:
        report['caveat'] = 'Unsafe/incomplete schema values or no Raw rows: no manufactured raw replay.'
    else:
        cams = sorted({c for data in raw.values() for c in data})
        for name, peak in zip(('baseline', 'integrated'), functions[:2]):
            obj, diagnostics, log = run(raw, cams, peak, functions[2])
            report[name] = dict(stats=obj._pass1_stats, final_stats=obj._final_stats,
                                peak_diagnostics=diagnostics, source_stdout=log,
                                pass1=summarize(raw, provenance, cams, obj._pass1_stats, obj._pass1_pairs),
                                final=summarize(raw, provenance, cams, obj._final_stats, obj.wand_data_filtered))
            refs = {f'{f}:{c}': [v['Filtered_Small'], v['Filtered_Large']]
                    for (f, c), v in reference.items() if len(v) == 2}
            for stage in ('pass1', 'final'):
                ids = report[name][stage]['selected_identities']
                values = {key: [r[4:] for r in records] for key, records in ids.items()}
                report[name][stage]['reference_comparison'] = compare(refs, values)
        report['baseline_integrated_comparison'] = {stage: compare(report['baseline'][stage]['selected_identities'],
                                                                report['integrated'][stage]['selected_identities'])
                                                   for stage in ('pass1', 'final')}
        report['changed_stat_cameras'] = [c for c in cams if report['baseline']['stats'].get(c) != report['integrated']['stats'].get(c)]
        # Keep full identities in memory for exact comparisons, not private-row
        # copies in the report. Differences retain exact frame/camera keys.
        for name in ('baseline', 'integrated'):
            for stage in ('pass1', 'final'):
                selected = report[name][stage].pop('selected_identities')
                report[name][stage]['ordered_identity_sha256'] = hashlib.sha256(
                    json.dumps(selected, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    report['sha256_after'] = digest(path)
    assert before == report['sha256_after']
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', '--inputs', nargs='+', required=True, dest='inputs')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    allowed = ROOT / '.opencode/outputs/wand_main_fingerprint_repair'
    assert out.is_relative_to(allowed), 'Outputs must remain in wand_main_fingerprint_repair'
    out.parent.mkdir(parents=True, exist_ok=True)
    for sub in ('tmp', 'cache'):
        (allowed / sub).mkdir(parents=True, exist_ok=True)
    for key in ('TMP', 'TEMP', 'TMPDIR'):
        os.environ[key] = str(allowed / 'tmp')
    for key in ('XDG_CACHE_HOME', 'MPLCONFIGDIR', 'NUMBA_CACHE_DIR'):
        os.environ[key] = str(allowed / 'cache')
    functions = extract()
    report = dict(production_integration=True, source_sha256_before=digest(SOURCE), helper_sha256=digest(__file__),
                  source_lf_sha256=normalized_source_digest(), integrated_peak_ast_sha256=INTEGRATED_PEAK_AST_SHA256,
                  baseline_definition='Legacy reconstructed by removal of exactly the unique checked three-node guard; AST fingerprint matches pre-integration method.',
                  integrated_definition='Actual production peak method compiled unchanged; no extra guard or observations inserted.',
                  legacy_source_sha256=LEGACY_SOURCE_SHA256, legacy_peak_ast_sha256=LEGACY_PEAK_AST_SHA256,
                  unchanged_generator_ast_sha256=LEGACY_GENERATOR_AST_SHA256,
                  python=sys.executable, numpy=np.__version__, datasets=[],
                  limitations=['Filtered labels are references, not ground truth.',
                               'Median fallback and metric selection can mislabel overlapping populations.',
                               'No GUI, images, physical calibration or detection verified.',
                               'Source hash binding intentionally requires review on source changes.'])
    for path in args.inputs:
        result = replay_csv(Path(path), functions)
        report['datasets'].append(result)
        print(Path(path).name, result['inventory']['statuses'],
              {name: [result[name][s]['valid_frames'] for s in ('pass1', 'final')]
               for name in ('baseline', 'integrated') if name in result}, flush=True)
    report['source_sha256_after'] = digest(SOURCE)
    assert report['source_sha256_before'] == report['source_sha256_after']
    def default(value):
        if isinstance(value, np.generic):
            return value.item()
        raise TypeError(type(value).__name__)
    out.write_text(json.dumps(report, indent=2, default=default, allow_nan=False)+'\n', encoding='utf-8')
    lines = ['# Production radius-guard integration replay', '', 'Baseline is the fingerprint-verified legacy method. Integrated is actual production, not a second injected guard.', 'Counts are pass1 / final. Filtered labels are references only.', '']
    for d in report['datasets']:
        lines += [f"## {Path(d['input']).name}", f"- Rows/status: {d['inventory']['rows']} / {d['inventory']['statuses']}",
                  f"- SHA256 before/after: {d['sha256_before']} / {d['sha256_after']}"]
        for name in ('baseline', 'integrated'):
            if name in d:
                lines += [f"- {name}: {d[name]['pass1']['valid_frames']} / {d[name]['final']['valid_frames']}"]
        if 'baseline_integrated_comparison' in d:
            lines += [f"- Ordered identity changes: { {s: len(v['changed_camera_frames']) for s, v in d['baseline_integrated_comparison'].items()} }"]
            raw = d['inventory']['by_status']['Raw']
            lines += [f"- Raw inventory: {raw['frames']} frames, cameras {raw['cameras']}, {len(raw['missing_frame_ids'])} missing IDs, {raw['missing_camera_cells']} missing camera cells.",
                      f"- Changed stat cameras: {d['changed_stat_cameras']}"]
            for name in ('baseline', 'integrated'):
                ref = d[name]['final']['reference_comparison']
                lines += [f"- {name} final vs reference: {ref['common_camera_frames']} common camera-frames, {len(ref['changed_camera_frames'])} changed, {len(ref['only_left'])} reference-only, {len(ref['only_right'])} selected-only."]
        else:
            lines += [f"- Caveat: {d.get('caveat')}"]
    lines += ['', '## Limitations', *['- '+s for s in report['limitations']]]
    out.with_suffix('.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
