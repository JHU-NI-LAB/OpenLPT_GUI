"""Deterministic regressions of the actual production overlap guard and fallback.

Run: OpenLPT python -B -m unittest discover -s test -p test_wand_radius_filter_regression.py -v
No attachments, prior reports, GUI imports or optional test runner required.
"""
import contextlib
import csv
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers.wand_radius_experiment import ROOT, SOURCE_SHA256, normalized_source_digest, extract, load_csv, production_peak, run


class ProductionGuardRegression(unittest.TestCase):
    def test_actual_production_rejects_touching_closed_supports_without_shared_sample(self):
        counts = np.ones(60, dtype=int)
        counts[8:15] = counts[16:23] = 30
        counts[10], counts[20], counts[15] = 100, 90, 0
        # Anchors set exact one-unit histogram bins. Bin 15 is empty;
        # both expanded supports terminate at its center, 15.5.
        radii = np.concatenate(([0., 60.], np.repeat(np.arange(60, dtype=float)+.5, counts)))
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            legacy = extract()[0](SimpleNamespace(), radii, 0)
            result = production_peak()(SimpleNamespace(), radii, 0)
        self.assertIsNotNone(legacy)
        self.assertIsNone(result)
        self.assertIn('S[7.5, 15.5], L[15.5, 23.5]', log.getvalue())
        self.assertIn('shared samples=0', log.getvalue())

    def test_actual_production_rejects_same_lobe_supports(self):
        counts = np.ones(60, dtype=int)
        counts[10:25] = 30
        counts[12], counts[22] = 100, 90
        radii = np.repeat(np.arange(60, dtype=float), counts)
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            result = production_peak()(SimpleNamespace(), radii, 7)
        self.assertIsNone(result)
        self.assertIn('Cam 7', log.getvalue())
        self.assertIn('Discarding peak stats', log.getvalue())
        self.assertIn('overlap', log.getvalue())
        self.assertNotIn('Falling back', log.getvalue())


class RadiusRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.functions = extract()

    def peak(self, values, candidate=True):
        obj = SimpleNamespace(_diag={})
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            result = self.functions[int(candidate)](obj, np.asarray(values), 0)
        return result, log.getvalue()

    def execute(self, raw, candidate=True):
        return run(raw, [0], self.functions[int(candidate)], self.functions[2])[0]

    def separated(self, unequal=False, outliers=False):
        rng = np.random.default_rng(824)
        raw, truth = {}, {}
        for f in range(180):
            # Independent manufactured labels and spatial centers, not inferred
            # using the histogram under test. The populations are unambiguous.
            s = [10.+f/1000, 20., float(70+rng.uniform(-1, 1)), .9]
            l = [50.+f/1000, 60., float(100+rng.uniform(-1, 1)), .8]
            pts = [s, l]
            if unequal:
                pts += [[15., 25., float(70+rng.uniform(-1, 1)), .1] for _ in range(2)]
            if outliers or f == 0:
                pts += [[-1., -2., 40., .01], [-3., -4., 130., .01]]
            raw[f] = {0: pts}
            truth[f] = [s, l]
        return raw, truth

    def assert_truth(self, obj, raw, truth):
        self.assertEqual(set(obj.wand_data_filtered), set(truth))
        for f, expected in truth.items():
            got = obj.wand_data_filtered[f][0]
            self.assertTrue(all(a is b for a, b in zip(got, expected)))
            self.assertIsNot(got[0], got[1])
            self.assertEqual(got[0][:2], [10.+f/1000, 20.])
            self.assertEqual(got[1][:2], [50.+f/1000, 60.])
            self.assertTrue(all(any(p is q for q in raw[f][0]) for p in got))

    def test_integrated_source_binding(self):
        self.assertEqual(normalized_source_digest(), SOURCE_SHA256)

    def test_separated_modes_stats_and_original_identities_unchanged(self):
        raw, truth = self.separated()
        a, b = self.execute(raw, False), self.execute(raw)
        self.assertEqual(a._pass1_stats, b._pass1_stats)
        self.assertEqual(a._final_stats, b._final_stats)
        self.assert_truth(a, raw, truth)
        self.assert_truth(b, raw, truth)
        self.assertAlmostEqual(b._final_stats[0]['s'][0], 70., delta=.2)
        self.assertAlmostEqual(b._final_stats[0]['l'][0], 100., delta=.2)

    def test_same_lobe_original_degeneracy_guard_and_exact_existing_fallback(self):
        counts = np.ones(60, dtype=int)
        counts[10:25] = 30
        counts[12], counts[22] = 100, 90
        radii = np.repeat(np.arange(60, dtype=float), counts)
        old, _ = self.peak(radii, False)
        new, log = self.peak(radii)
        self.assertIsNotNone(old)
        self.assertEqual(old[0], old[1])
        self.assertIsNone(new)
        self.assertIn('Discarding peak stats', log)
        self.assertRegex(log, r'shared samples=[1-9]\d*')
        raw = {0: {0: [[float(i), 1., float(r), .1] for i, r in enumerate(radii)]}}
        obj, diagnostics, log = run(raw, [0], self.functions[1], self.functions[2])
        self.assertTrue(diagnostics[0]['overlap_guard_rejected'])
        self.assertIn('Falling back to Median Zoning', log)
        median = np.median(radii)
        for label, values in (('s', radii[radii <= median]), ('l', radii[radii > median])):
            self.assertEqual(obj._pass1_stats[0][label], (np.mean(values), max(.5, np.std(values))))

    def test_unequal_detection_weights_and_metric_distractors(self):
        raw, truth = self.separated(unequal=True)
        obj = self.execute(raw)
        self.assert_truth(obj, raw, truth)

    def test_far_outlier_contamination(self):
        raw, truth = self.separated(outliers=True)
        obj = self.execute(raw)
        self.assert_truth(obj, raw, truth)

    def test_overlapping_true_populations_unsafe_limitation(self):
        # Known physical labels are independent of instantaneous radius order.
        # An accepted pair is NOT proof of correct identity in this regime.
        raw, truth = {}, {}
        for f in range(180):
            s = [10., float(f), float(70+4*np.sin(f)), .1]
            l = [50., float(f), float(72+4*np.cos(f)), .9]
            raw[f], truth[f] = {0: [s, l]}, [s, l]
        obj = self.execute(raw)
        mismatched = [f for f, v in obj.wand_data_filtered.items()
                      if any(a is not b for a, b in zip(v[0], truth[f]))]
        self.assertGreater(len(obj.wand_data_filtered), 0)
        self.assertGreater(len(mismatched), 0, 'Reassess diagnostic if selection changes')
        print(f'KNOWN LIMITATION: overlapping true populations: accepted={len(obj.wand_data_filtered)}, mislabelled={len(mismatched)}')

    def test_equal_single_radius_cannot_yield_pair(self):
        raw = {f: {0: [[10., 20., 90., .1], [50., 60., 90., .9]]} for f in range(12)}
        self.assertIsNone(self.peak([90.]*24)[0])
        self.assertEqual(self.execute(raw).wand_data_filtered, {})

    def test_empty_and_fewer_than_ten(self):
        for radii in ([], [70., 100.]*4):
            self.assertIsNone(self.peak(radii)[0])
        self.assertEqual(self.execute({}).wand_data_filtered, {})
        self.assertEqual(self.execute({0: {0: [[1., 2., 70., 1.], [3., 4., 100., 1.]]}}).wand_data_filtered, {})

    def test_source_selection_strict_boundary_not_inclusive(self):
        # Isolate the unchanged source selection with controlled statistics.
        peak = lambda self, rs, cam: ((70., .5), (100., .5))
        for inside in (False, True):
            s, l = (np.nextafter(73.5, 70.), np.nextafter(105., 100.)) if inside else (73.5, 105.)
            raw = {f: {0: [[10., 20., float(s), 1.], [50., 60., float(l), 1.]]} for f in range(6)}
            obj = run(raw, [0], peak, self.functions[2])[0]
            self.assertEqual(len(obj.wand_data_filtered), 6 if inside else 0)

    def test_csv_raw_inventory_not_mixed_with_reference_labels(self):
        # Fixtures are generated locally; neither attachment access nor prior
        # experiment artifacts are needed to run the suite.
        out = ROOT / '.opencode/outputs/wand_main_fingerprint_repair/tmp'
        out.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=out) as directory:
            path = Path(directory) / 'synthetic.csv'
            for include_raw in (True, False):
                with path.open('w', newline='', encoding='utf-8') as stream:
                    writer = csv.writer(stream)
                    writer.writerow(['Frame', 'Camera', 'Status', 'PointIdx', 'X', 'Y', 'Radius', 'Metric'])
                    if include_raw:
                        for i in range(3):
                            writer.writerow([17, 6, 'Raw', i, 10+i, 20+i, 70+i*15, .1+i*.1])
                    writer.writerow([17, 6, 'Filtered_Small', 0, 10, 20, 70, .1])
                    writer.writerow([17, 6, 'Filtered_Large', 1, 11, 21, 85, .2])
                raw, provenance, reference, inventory = load_csv(path)
                self.assertFalse(inventory['unsafe'])
                self.assertEqual(len(provenance), 3 if include_raw else 0)
                self.assertEqual(len(reference[(17, 6)]), 2)
                if include_raw:
                    self.assertEqual(len(raw[17][6]), 3)
                    self.assertEqual(inventory['by_status']['Raw']['points_per_camera_frame'], {3: 1})
                else:
                    self.assertEqual(raw, {})


if __name__ == '__main__':
    unittest.main(verbosity=2)
