import pytest

from fias_ed_engine.intervals import CodedSegment as S, segments_to_intervals, transition_matrix
from fias_ed_engine.rules import load_rules

R = load_rules("fias_rules")


def test_empty_audio_is_all_silence():
    assert segments_to_intervals([], 9000, R) == [10, 10, 10]


def test_partial_last_interval_counts():
    assert len(segments_to_intervals([], 7000, R)) == 3


def test_largest_coverage_wins():
    segs = [S(0, 1000, 5), S(1000, 3000, 4)]
    assert segments_to_intervals(segs, 3000, R) == [4]


def test_tie_goes_to_earliest_start():
    segs = [S(0, 1500, 5), S(1500, 3000, 8)]
    assert segments_to_intervals(segs, 3000, R) == [5]


def test_segment_spanning_intervals():
    segs = [S(500, 7000, 5)]
    assert segments_to_intervals(segs, 9000, R) == [5, 5, 5]


def test_gap_interval_is_silence():
    segs = [S(0, 3000, 4), S(6000, 9000, 8)]
    assert segments_to_intervals(segs, 9000, R) == [4, 10, 8]


def test_invalid_segment_rejected():
    with pytest.raises(ValueError):
        segments_to_intervals([S(3000, 1000, 5)], 9000, R)
    with pytest.raises(ValueError):
        segments_to_intervals([S(0, 1000, 11)], 9000, R)


def test_matrix_pads_with_10():
    m = transition_matrix([4, 8], R)
    assert m[10 - 1][4 - 1] == 1   # 10→4 (padding inicial)
    assert m[4 - 1][8 - 1] == 1    # 4→8
    assert m[8 - 1][10 - 1] == 1   # 8→10 (padding final)
    assert sum(map(sum, m)) == 3


def test_matrix_empty_sequence():
    m = transition_matrix([], R)
    assert m[9][9] == 1 and sum(map(sum, m)) == 1
