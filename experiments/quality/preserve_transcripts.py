"""Preserve local interaction records privately; never publish raw session logs.

Copies raw runtime records without displaying them. The portable interaction
export omits internal reasoning/system context; includes user/assistant messages,
tool calls and tool outputs. Completeness of runtime capture is not certified.
"""
import argparse
import hashlib
import json
from pathlib import Path


def preserve(sources, output):
    output.mkdir(parents=True, exist_ok=False)
    entries = []
    for source in sources:
        raw = source.read_bytes()
        (output / source.name).write_bytes(raw)
        visible = []; models = set(); mappings = []; prompts = []
        for line_no, line in enumerate(raw.splitlines(), 1):
            try:
                record = json.loads(line)
            except ValueError:
                continue  # A live session may end with an incomplete record.
            payload = record.get('payload', {})
            if record.get('type') == 'turn_context':
                models.add(payload.get('model', 'unrecorded'))
            if record.get('type') != 'response_item':
                continue
            kind = payload.get('type')
            if (kind == 'message' and payload.get('role') in ('user', 'assistant')
                    and payload.get('channel') not in ('analysis', 'summary')) or kind in (
                    'function_call', 'custom_tool_call', 'function_call_output', 'custom_tool_call_output'):
                visible.append({'source_line': line_no, **record})
                if payload.get('role') == 'user': prompts.append(line_no)
                if kind in ('function_call', 'custom_tool_call'):
                    text = payload.get('arguments', '') + payload.get('input', '')
                    for target in ['fir_audio_top.v', 'candidate_reference.py', 'prepare_vectors.py', 'experiments/quality']:
                        if target in text:
                            mappings.append({'source_path_marker': target, 'tool_line': line_no,
                                'preceding_user_prompt_line': prompts[-1] if prompts else None,
                                'note': 'Path mention in tool call; not by itself proof of a successful write'})
        export = output / (source.stem + '.interaction.jsonl')
        export.write_text(''.join(json.dumps(v) + '\n' for v in visible), encoding='utf-8')
        entries.append({'source_filename': source.name, 'raw_sha256': hashlib.sha256(raw).hexdigest(),
            'raw_bytes': len(raw), 'interaction_sha256': hashlib.sha256(export.read_bytes()).hexdigest(),
            'visible_records': len(visible), 'recorded_runtime_models': sorted(models),
            'source_to_prompt_candidates': mappings})
    index = {'scope': 'Private local snapshot; no external publication',
        'completeness': 'All available records copied at capture time; live session still open',
        'entries': entries}
    (output / 'index.json').write_text(json.dumps(index, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'preserved_sessions': len(entries), 'output': str(output)}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('sources', nargs='+', type=Path)
    a = p.parse_args()
    preserve(a.sources, a.output)
