def validate_gst_rate(

    expected_rate,

    detected_rate
):

    try:

        expected_rate = float(expected_rate)

        detected_rate = float(detected_rate)

        if expected_rate == detected_rate:

            return {

                "valid": True,

                "message":

                f"Correct GST {detected_rate}%"
            }

        else:

            return {

                "valid": False,

                "message":

                f"Expected GST {expected_rate}% but found {detected_rate}%"
            }

    except Exception as e:

        return {

            "valid": False,

            "message": str(e)
        }