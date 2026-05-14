def validate_amounts(

    subtotal,

    gst_amount,

    final_total
):

    try:

        subtotal = float(subtotal)

        gst_amount = float(gst_amount)

        final_total = float(final_total)

        calculated_total = (

            subtotal + gst_amount
        )

        difference = abs(

            calculated_total - final_total
        )

        # ROUNDING ALLOWED
        if difference <= 1:

            return {

                "valid": True,

                "calculated_total":

                    round(calculated_total, 2),

                "message":

                    "Invoice totals are correct"
            }

        else:

            return {

                "valid": False,

                "calculated_total":

                    round(calculated_total, 2),

                "message":

                    f"Expected total "
                    f"{calculated_total} "
                    f"but found "
                    f"{final_total}"
            }

    except Exception as e:

        return {

            "valid": False,

            "message": str(e)
        }