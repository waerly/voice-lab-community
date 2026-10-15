"""Validate the discrete controls supported by the installed MLX Spark model."""
import secrets


def spark_controls(value, mode):
    levels = (0, .5, 1, 1.5, 2)
    pitch, speed = value.get('spark_pitch', 1), value.get('spark_speed', 1)
    seed = value.get('spark_seed', 42)
    change = value.get('spark_new_voice', False)
    if type(pitch) not in (int, float) or pitch not in levels:
        raise ValueError('音高必须选择有效档位')
    if type(speed) not in (int, float) or speed not in levels:
        raise ValueError('语速必须选择有效档位')
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError('无效的声音候选编号')
    if type(change) is not bool:
        raise ValueError('无效的换声音选项')
    if mode == 'clone':
        if change:
            raise ValueError('换一个声音仅用于创建模式')
        return dict(spark_pitch=1, spark_speed=1, spark_seed=42)
    if change:
        seed = (seed + 1 + secrets.randbelow(2**32 - 1)) % 2**32
    return dict(spark_pitch=pitch, spark_speed=speed, spark_seed=seed)
