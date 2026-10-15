import unittest
from spark_controls import spark_controls


class SparkControlTests(unittest.TestCase):
    def test_discrete_levels_and_defaults(self):
        self.assertEqual(spark_controls({}, 'design')['spark_seed'], 42)
        for level in (0, .5, 1, 1.5, 2):
            self.assertEqual(spark_controls(dict(spark_pitch=level, spark_speed=level), 'design')['spark_speed'], level)
        for bad in (-1, .7, 3, float('nan'), True, '1'):
            with self.assertRaises(ValueError): spark_controls(dict(spark_pitch=bad), 'design')

    def test_new_candidate_and_repeat(self):
        result = spark_controls(dict(spark_seed=42, spark_new_voice=True), 'design')
        self.assertNotEqual(result['spark_seed'], 42)
        self.assertEqual(spark_controls(result, 'design'), result)
        for bad in (-1, 2**32, 1.5, True):
            with self.assertRaises(ValueError): spark_controls(dict(spark_seed=bad), 'design')

    def test_clone_ignores_creation_controls(self):
        self.assertEqual(spark_controls(dict(spark_pitch=2, spark_speed=.5, spark_seed=99), 'clone'),
                         dict(spark_pitch=1, spark_speed=1, spark_seed=42))
        with self.assertRaises(ValueError): spark_controls(dict(spark_new_voice=True), 'clone')


if __name__ == '__main__': unittest.main()
