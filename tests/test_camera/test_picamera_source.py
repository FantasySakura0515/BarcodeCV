from backend.camera.picamera_source import PiCameraSource


def test_parse_camera_list_output_parses_cli_camera_rows():
    output = """
    Available cameras
    -----------------
    0 : imx708 [4608x2592 10-bit RGGB] (/base/axi/pcie@120000/rp1/i2c@88000/imx708@1a)
    1 : imx219 [3280x2464 10-bit BGGR] (/base/axi/pcie@120000/rp1/i2c@80000/imx219@10)
    """

    cameras = PiCameraSource._parse_camera_list_output(output)

    assert cameras == [
        {"Num": 0, "Model": "imx708", "Id": "cli0"},
        {"Num": 1, "Model": "imx219", "Id": "cli1"},
    ]
