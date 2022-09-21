import fire
from gpt2textgen import TextGen


def interact():
    tg = TextGen(checkpoint_dir='checkpoint', temperature=0.8)
    transcript = ""

    initialprompt = "James S. Brady Press Briefing Room\n"
    text = tg.get_text(initialprompt, endtoken="\nQ", post_process=False, remove_prefix=False)
    print(text)
    transcript += text

    while True:
        raw_text = input("Q ")
        while not raw_text:
            raw_text = input("Q ")

        prompt = f"{transcript}\nQ {raw_text}"[-1023:]
        text = tg.get_text(prompt, endtoken="\nQ", post_process=False)
        print(text)
        #transcript += text


if __name__ == "__main__":
    fire.Fire(interact)
