"""Transparent editorial refinement of the small, original distillation pilot.

These are training labels, never runtime canned responses. This review is by the
coding agent, not independent human annotation. Original teacher text is retained.
"""
import hashlib
import json
import shutil
from pathlib import Path

from .public_baseline import write_json

REPLIES = {
"slow-zombies": [
"You can walk away until you need to sleep. Isn't the scary part knowing they'll still be coming when you're exhausted?",
"That assumes you have somewhere safe to go. A slow threat becomes dangerous when exits disappear and the group starts making compromises.",
"A slow zombie is an unpaid bill with teeth. You can ignore it today, but eventually it's waiting at your door.",
"Walking away works while everyone is healthy. Add an injured friend or a locked stairwell, and speed isn't the only problem.",
"Fast zombies give you a pursuit scene; slow ones give you a shift that never ends. Which pressure wears a group down first?",
"I'd separate physical danger from suspense. A slower threat gives the audience time to notice mistakes before the characters do.",
"The fast ones scare your legs. The slow ones ruin your calendar, because every plan now includes checking whether the undead have arrived.",
"Both can work. I care more about who makes the difficult choice when somebody in the group can't keep up.",
],
"group-trust": [
"But who keeps watch when everybody finally falls asleep? A locked door helps; it doesn't replace people you can depend on.",
"Trusting nobody is also a risk. I'd want a way to test cooperation in small steps before handing over all the supplies.",
"Congratulations, we've survived the zombies and invented the world's loneliest apartment building. Who's bringing soup when the person with the key gets sick?",
"I'd start with a small shared task and clear limits. That gives people a chance to earn trust without gambling the entire food supply.",
"Sharing a little could reveal who's willing to help. How would you distinguish caution from a policy that slowly breaks the group apart?",
"We shouldn't confuse a secure boundary with complete isolation. The question is which arrangement gives the group the best chance over time.",
"A locked pantry sounds sensible until everyone starts hiding crackers in their shoes. Maybe the real monster is our terrible group chat.",
"I'd make the inventory visible and agree on portions together. People handle limits better when they understand the reasons and see the same rules applied.",
],
"jupiter": [
"A storm that lasts that long changes your sense of scale. What would it mean to study weather whose story stretches beyond one person's lifetime?",
"The interesting comparison is duration, not which planet has more impressive weather. Jupiter gives us a very different atmosphere to investigate.",
"Earth cancels a picnic; Jupiter keeps a storm as a landmark. That's a fairly dramatic difference in what counts as a bad forecast.",
"It makes a distant planet feel less abstract. A recognizable storm gives people something concrete to follow while learning about a much larger world.",
"The Great Red Spot makes me wonder how scientists notice slow changes. What can repeated observations reveal that one beautiful image cannot?",
"We can admire the scale without pretending it behaves exactly like an Earth hurricane. Similar-looking features don't necessarily share every underlying process.",
"Imagine trying to name a storm and discovering it outlasts the naming committee. Jupiter really commits to a recurring character.",
"I'd use that contrast to invite curiosity, rather than make Earth's weather seem unimportant. Familiar experiences can be a useful doorway into unfamiliar science.",
],
"moonlight": [
"It's sunlight taking a longer route into the scene. Does knowing that change the mood for you, or make it more remarkable?",
"The useful distinction is reflection versus a light source. The Moon reflects sunlight; it isn't generating that visible glow itself.",
"The Sun does the lighting and the Moon gets the romantic close-up. That's an excellent arrangement if you're the Moon's publicity team.",
"I like how a simple fact can change what someone notices. The scene stays beautiful, but now there's a physical connection behind the atmosphere.",
"That reflected light can make an ordinary place feel unfamiliar. What would you change in the scene to keep that feeling without explaining it aloud?",
"I'd keep the scientific explanation separate from the interpretation. Reflected sunlight is the mechanism; mystery is what the storyteller does with it.",
"Moonlight is the night borrowing a lamp from the day. Somehow the borrowed version gets all the poetry.",
"We don't have to choose between understanding the light and enjoying the mood. Knowing where it comes from can add another layer to the experience.",
],
"vr-set": [
"I'd put one small discovery near each seat, then let viewers decide what to inspect. What could reward curiosity without pulling attention away from the conversation?",
"Interactivity needs a purpose. If every object flashes for attention, viewers spend the episode operating a room instead of following what anyone says.",
"Give the red lamp one mysterious button, and half the audience will become unpaid lamp researchers. The reward had better be worth the investigation.",
"Start with readable paths and a few useful interactions. The two cups can be inspectable props without making every object a mandatory task.",
"Could a spectator quietly explore while still hearing the hosts? I'd want curiosity to feel welcome even when someone chooses not to participate.",
"The scene tells us about four seats and two cups, but it gives no audience count. Room objects aren't evidence of how many people are watching.",
"Let someone discover a tiny backstage joke instead of another instruction panel. A room can have personality without turning into a flashing checklist.",
"I'd keep a clear route back to the main view. People should feel comfortable exploring because returning to the discussion is effortless.",
],
"game-team": [
"It might simplify balancing, but would it remove the reason to cooperate? I like moments where another person's different ability changes what the team can attempt.",
"Equal tools and balanced roles aren't the same thing. Different abilities can be balanced through limitations, useful combinations and situations where each role matters.",
"If everybody brings a hammer, our cooperative game becomes a very enthusiastic furniture accident. I'd rather give the team reasons to need each other.",
"I'd give everyone a useful starting action, then add complementary strengths. New players can contribute immediately while the team discovers deeper combinations.",
"What if a simple task has two equally useful approaches? That could let players find their own style before asking them to coordinate something difficult.",
"I'd test whether each ability creates meaningful choices. Variety that changes only the animation doesn't necessarily create a different role.",
"One player opens doors, another makes terrible distractions, and suddenly my natural talents have a job description. Cooperation should leave room for unusual contributions.",
"The important part is making every role understandable and worthwhile. Nobody should spend the whole session waiting for the one moment they're allowed to help.",
],
"music-silence": [
"Sometimes stopping the music makes the audience listen harder. What would happen if the next important sound were small enough that everyone had to lean in?",
"Constant volume isn't the same as sustained tension. A contrast can make the next sound matter more than another minute at the same intensity.",
"If the soundtrack never takes a breath, even the monster needs a quiet room. Silence can be the moment the audience realizes they're holding theirs.",
"I'd choose the silence around a specific story beat. Used with purpose, a pause can give an emotion room to land rather than simply draining energy.",
"A quiet moment can turn our attention toward the characters instead of the music. Which detail would you want the audience to notice there?",
"The question is what changes during the pause. If the scene gains anticipation or a new detail, silence is doing narrative work.",
"Silence is the soundtrack briefly turning off its notifications. Suddenly we notice the suspicious little noise we were happily ignoring.",
"I wouldn't remove music just because silence seems sophisticated. I'd compare both versions and ask which makes the character's situation easier to feel.",
],
"radio-ghost": [
"Checking the equipment makes sense, but the unplugged microphone is already an interesting clue. What would convince you the voice isn't coming from another ordinary source?",
"I'd verify where the sound actually originates before proposing an explanation. An unexplained event isn't evidence for whichever theory makes the best story.",
"I'd check the equipment too, while politely informing the microphone that unpaid guest appearances require advance booking. No reason to abandon manners during a haunting.",
"I'd stay with the group, check the connections and keep listening carefully. We can be curious without deciding immediately that the room is dangerous or supernatural.",
"A sensible character can make the mystery stronger by ruling out easy explanations. Which test would you show the audience before letting the voice speak again?",
"Unplugged and silent are different claims. The story gives us a voice despite the disconnection, so an explanation needs to account for that detail.",
"Maybe the ghost finally found a podcast with no subscription fee. I'd still ask it to use the guest microphone and stop alarming the furniture.",
"I'd let someone investigate while another person watches the rest of the room. A clear shared plan can keep the scene tense without making everyone act recklessly.",
],
"film-sound": [
"A loud cue can startle me, but a quiet scene makes me search for the threat. Which feeling do you want to last after that moment?",
"The word 'always' is doing too much work there. A sudden sound and sustained anticipation produce different effects, so I'd judge them against the scene's purpose.",
"A jump scare knocks on the door; a quiet scene makes me wonder who has a key. Both work, but only one follows me into the hallway.",
"I'd look at what the character knows and what the audience knows. Silence can give that difference time to become uncomfortable.",
],
"mars-rover": [
"Borrowed eyes is a lovely way to describe it. What observation would make the landscape feel like a real place instead of just a distant image?",
"The rover provides observations; interpreting them is the next step. I like the analogy as long as we remember how much careful work sits behind each conclusion.",
"A rover is our very expensive friend who actually sends photos from the trip. I'd still like to know who gets to choose the interesting rock.",
"It gives people a concrete connection to exploration. Following a few observations over time can be more engaging than trying to understand an entire planet at once.",
],
"future-library": [
"Would you compare what happened, or what each ending meant to its reader? That difference could turn a confusing book club into an interesting conversation.",
"We'd need to distinguish changes in the book from differences in interpretation. In this fictional library, both could affect what readers report.",
"The book club would need an incident board and several colors of string. Imagine accusing someone of spoilers when their ending hasn't happened to you.",
"I'd ask readers to describe their version before arguing about the best ending. A shared starting point could make the differences part of the fun.",
],
"island-choice": [
"I'd want to know what the group loses by waiting until morning. Could one person assess the radio while the others decide whether the cave is worth the risk?",
"I'd compare urgency, likely benefit and what can safely wait. Curiosity alone doesn't establish that exploring the cave is the better use of limited daylight.",
"The cave has mystery, but the radio has the attractive feature of potentially getting us off this island. Adventure can wait until we've considered room service elsewhere.",
"I'd prioritize a realistic chance to contact help, then reassess with the group. Keeping people informed matters as much as choosing the most exciting task.",
]}


def review_snapshot(source, output):
    source, output = Path(source), Path(output)
    if output.exists():
        raise FileExistsError("Use a new reviewed curriculum directory")
    (output / "data").mkdir(parents=True)
    records = []
    splits = {k: [] for k in ("train", "val", "test")}
    counts = {}
    edits = []
    for line in (source / "conversations.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        index = counts.get(row["topic"], 0)
        counts[row["topic"]] = index + 1
        target = REPLIES[row["topic"]][index]
        original = row["messages"][-1]["content"]
        row["original_teacher_reply"] = original
        row["messages"][-1]["content"] = target
        row["parent_id"] = row["id"]
        row["id"] = hashlib.sha256(json.dumps(row["messages"], sort_keys=True).encode()).hexdigest()
        row["transform"] = "Coding-agent editorial rewrite for coherence, grounding, specificity and distinct fictional character voice; not independent human review"
        records.append(row)
        edits.append({"id": row["id"], "parent_id": row["parent_id"], "before": original, "after": target, "reason": row["transform"]})
        splits[row["upstream_split"]].append({"episode_id": row["id"], "series_id": row["topic"], "text": json.dumps(row["messages"])})
    if any(counts[k] != len(v) for k, v in REPLIES.items()):
        raise ValueError("Review rows do not match the frozen original curriculum")
    for split, rows in splits.items():
        (output / "data" / (split + ".jsonl")).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    for name, rows in [("conversations.jsonl", records), ("editorial-review.jsonl", edits)]:
        (output / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    manifest = json.loads((source / "public-sources.json").read_text(encoding="utf-8"))
    manifest.update(method="Sequence-level distillation pilot with transparent editorial refinement",
                    parent_corpus_sha256=manifest["corpus_sha256"],
                    corpus_sha256=hashlib.sha256((output / "conversations.jsonl").read_bytes()).hexdigest(),
                    editorial_review="All 80 targets revised by the coding agent; no independent human review",
                    editorial_log="editorial-review.jsonl", validation_scope="Entire topics are disjoint; evaluation targets are editorial references, not objective truth for opinions")
    write_json(output / "public-sources.json", manifest)
    write_json(output / "data/corpus_report.json", manifest)
    (output / "UPSTREAM-DATASET-CARD.md").write_text("# Reviewed original podcast curriculum\n\n" + json.dumps(manifest, indent=2), encoding="utf-8")
    shutil.copy2(source / "teacher-responses.jsonl", output / "teacher-responses.jsonl")
    return manifest
