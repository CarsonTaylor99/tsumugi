# Tier 0 synthetic fixture (docs/10): authored by hand, never extracted from
# a game. Exercises every construct the Ren'Py adapter claims to support.

define e = Character("エリカ")
define m = Character("真琴", color="#c8ffc8")
default player_name = "アキラ"

label start:
    scene bg classroom
    with fade

    "教室の窓から、夕日が差し込んでいた。"

    e "先輩……ずっと、言いたいことがあったんです。"

    e happy "えへへ、{i}やっと{/i}言えました!"

    m "おいおい、[player_name]、聞いてるのか?"

    "彼女は{b}真剣な{/b}顔で、こちらを見つめている。{w=0.5}沈黙が続いた。"

    e "この{rb}運命{/rb}{rt}さだめ{/rt}を、受け入れるしかないんです。{p}それでも——"

    "「引用符は \"こう\" 書く」と黒板に書いてあった。"

    "一行目\n二行目——改行を含む台詞。"

    "波括弧のリテラルは {{こう}} 書き、角括弧は [[こう]] 書く。"

    menu:
        "彼女に返事をする":
            jump reply
        "黙っている" if True:
            jump silent

label reply:
    "Non-canonical apostrophe escape: \'quoted\' — the extractor must skip this line loudly."
    e "ありがとう、先輩!" with vpunch
    m "ふん、勝手にしろ。" nointeract
    "The Teacher" "静かにしなさい!"
    return

label silent:
    $ affection += 1
    play music "audio/theme.ogg"
    voice "voice/ERK_0042.ogg"
    e "……そうですか。{nw}"
    return
