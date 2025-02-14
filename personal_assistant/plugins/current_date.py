import datetime


def get_output():
    # returns human readable current day, date and time
    human_readable = datetime.datetime.now().strftime("%c")

    return {
        "plugin_name": "datetime",
        "output": f"Current date and time: {human_readable}",
    }


if __name__ == "__main__":
    result = get_output()
    print(result["output"])
