from retail_counter.preview import detection_label


def test_preview_uses_person_wording_for_full_body_box():
    assert detection_label(0.83) == "PERSON 83%"
