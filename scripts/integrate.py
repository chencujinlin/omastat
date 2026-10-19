#!/usr/bin/env python3
"""Conservative omastat install integration; back up each changed user file."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

OLD_RULE_HASH = '0be316e1c5d1b234ac6fb523103bb6cc3f0ea5d698f43a07d6554bf11e46d3f7'


def replace(path, text):
    if path.is_file() and path.read_text() == text:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + '.bak.omastat.' + str(time.time_ns())))
    path.write_text(text)


def integrate(project, config_home, remove=False):
    config_home = Path(config_home)
    metadata = config_home / 'omarchy/omastat-install.json'
    saved = json.loads(metadata.read_text()) if metadata.is_file() else {}
    shell = config_home / 'omarchy/shell.json'
    data = json.loads(shell.read_text()) if shell.is_file() else {}
    layout = data.setdefault('bar', {}).setdefault('layout', {})
    for section in ('left', 'center', 'right'):
        if section in layout and not isinstance(layout[section], list):
            raise ValueError('bar section must be a list')
    if remove:
        if saved.get('barAdded'):
            for section in ('left', 'center', 'right'):
                if section in layout:
                    layout[section] = [e for e in layout[section] if not (isinstance(e, dict) and e.get('id') == 'chencu.omastat')]
        if shell.is_file():
            replace(shell, json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        rule = config_home / 'hypr/vitals.lua'
        bundled = Path(project) / 'hypr/vitals.lua'
        if rule.is_file() and rule.read_text() == bundled.read_text():
            if saved.get('previousRule') is not None:
                replace(rule, saved['previousRule'])
            elif saved.get('ruleAdded'):
                rule.unlink()
        metadata.unlink(missing_ok=True)
        return
    entries = [e for section in layout.values() if isinstance(section, list) for e in section]
    if not any(isinstance(e, dict) and e.get('id') == 'chencu.omastat' for e in entries):
        layout.setdefault('right', []).append({'id': 'chencu.omastat', 'metric': 'none'})
        saved['barAdded'] = True
        replace(shell, json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    rule = config_home / 'hypr/vitals.lua'
    bundled = Path(project) / 'hypr/vitals.lua'
    if not rule.exists():
        replace(rule, bundled.read_text())
        saved['ruleAdded'] = True
    elif hashlib.sha256(rule.read_bytes()).hexdigest() == OLD_RULE_HASH:
        saved.setdefault('previousRule', rule.read_text())
        replace(rule, bundled.read_text())
    elif rule.read_text() != bundled.read_text():
        print('omastat: 保留自定义 vitals.lua；omastat 使用新标题，不匹配旧的“系统监控”规则。')
    bindings = config_home / 'hypr/bindings.lua'
    if bindings.is_file():
        lines = bindings.read_text().splitlines(keepends=True)
        updated = ''.join(line.replace('"系统监控"', '"omastat"') if 'omarchy-vitals toggle' in line else line for line in lines)
        replace(bindings, updated)
    replace(metadata, json.dumps(saved, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config-home', type=Path, required=True)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--remove', action='store_true')
    args = parser.parse_args()
    integrate(args.project, args.config_home, args.remove)
