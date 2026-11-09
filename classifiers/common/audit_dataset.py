#!/usr/bin/env python3
"""Local-only TWI archive audit. No training, network, or inference calls."""
from __future__ import annotations
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))
_sys.path.insert(1,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())/'classifiers/common'))

import argparse
import csv
import hashlib
import itertools
import json
import math
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
import platform
import stat
import sys
import zipfile

from PIL import Image, ImageDraw, ImageFont, ImageOps, __version__ as pillow_version
import yaml

EXPECTED_SHA256 = '5c6fbd171586fe3ddacaf50fb50e209f43bec129e36b254f740aed0d99e79382'
ROOT = Path(__file__).resolve().parents[next(i for i,p in enumerate(Path(__file__).resolve().parents) if (p/'export-manifest.json').is_file())]


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def safe_extract(archive, destination, max_bytes=100_000_000, max_entries=1000):
    """Validate complete archive before writing; no traversal, links, or overwrites.

    Assumes no hostile concurrent process mutates destination during this local run.
    ZIP CRC checked before extraction. Destination is project-controlled.
    """
    destination = Path(destination).absolute()
    for component in [destination, *destination.parents]:
        if component.is_symlink():
            raise ValueError(f'Symlink extraction root: {component}')
    base = destination.resolve()
    with zipfile.ZipFile(archive) as z:
        infos = z.infolist()
        if len(infos) > max_entries or sum(i.file_size for i in infos) > max_bytes:
            raise ValueError('Archive size/entry limit exceeded')
        seen = set()
        for i in infos:
            name = i.filename
            rel = PurePosixPath(name)
            if (not name or '\\' in name or ':' in name or rel.is_absolute()
                    or '..' in rel.parts or name.rstrip('/') != rel.as_posix()
                    or rel.as_posix() in seen):
                raise ValueError(f'Unsafe/duplicate archive member: {name}')
            seen.add(rel.as_posix())
            kind = stat.S_IFMT(i.external_attr >> 16)
            if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise ValueError(f'Link/special archive member: {name}')
            if (kind == stat.S_IFDIR) != i.is_dir() and kind:
                raise ValueError(f'Inconsistent file type: {name}')
            target = destination.joinpath(*rel.parts)
            if not target.resolve().is_relative_to(base):
                raise ValueError(f'Target escapes extraction root: {name}')
            for component in [target, *target.parents]:
                if component.is_symlink():
                    raise ValueError(f'Existing symlink destination: {component}')
            if target.exists():
                if i.is_dir() and not target.is_dir():
                    raise ValueError(f'Directory conflicts: {name}')
                if not i.is_dir() and (not target.is_file() or target.read_bytes() != z.read(i)):
                    raise ValueError(f'Refusing overwrite: {name}')
        bad = z.testzip()
        if bad:
            raise ValueError(f'CRC failure: {bad}')
        for i in infos:
            target = destination.joinpath(*PurePosixPath(i.filename).parts)
            if i.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as f:
                    f.write(z.read(i))
        return [{'file': i.filename, 'bytes': i.file_size,
                 'compressed_bytes': i.compress_size, 'crc32': f'{i.CRC:08x}',
                 'directory': i.is_dir()} for i in infos]


def validate_labels(data, image_names):
    errors = []
    if not isinstance(data, dict):
        return ['YAML root must be a mapping']
    if data.get('task') != 'visual_tire_tread_condition_classification':
        errors.append('Unexpected task')
    if data.get('classes') != ['good', 'bad'] or data.get('review_label') != 'review':
        errors.append('Expected binary good/bad classes and review routing label')
    rows = data.get('images')
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        return errors + ['images must be a list of mappings']
    names = [r.get('file') for r in rows]
    if not all(isinstance(n, str) for n in names):
        return errors + ['All image filenames must be strings']
    if len(set(names)) != len(names):
        errors.append('Duplicate YAML image entries')
    if set(names) != set(image_names):
        errors.append(f'Image/label mismatch: unlabelled={sorted(set(image_names)-set(names))}; missing={sorted(set(names)-set(image_names))}')
    for r in rows:
        name = r['file']
        if r.get('label') not in ('good', 'bad', 'review'):
            errors.append(f'{name}: invalid label')
        c = r.get('confidence')
        if isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(c) or not 0 <= c <= 1:
            errors.append(f'{name}: invalid confidence')
        if type(r.get('review_required')) is not bool:
            errors.append(f'{name}: review_required must be boolean')
        if r.get('label') == 'review' and r.get('review_required') is not True:
            errors.append(f'{name}: review must require manual review')
        if not isinstance(r.get('reason'), str) or not r['reason'].strip():
            errors.append(f'{name}: missing reason')
        if 'duplicate_of' in r and (r['duplicate_of'] not in names or r['duplicate_of'] == name):
            errors.append(f'{name}: invalid duplicate_of reference')
    return errors


def hamming(a, b):
    return (int(a, 16) ^ int(b, 16)).bit_count()


def bits_hex(bits):
    n = 0
    for b in bits:
        n = (n << 1) | bool(b)
    return f'{n:016x}'


def fingerprint(path):
    with Image.open(path) as im:
        im.verify()
    with Image.open(path) as im:
        im.load()  # verify alone does not fully decode pixels
        fmt, mode, size = im.format, im.mode, im.size
        exif = im.getexif()
        sensitive = {str(k): str(v)[:160] for k, v in exif.items() if k in (271, 272, 306, 36867, 34853)}
        rgb = ImageOps.exif_transpose(im).convert('RGB')
        gray = rgb.convert('L')
        d = list(gray.resize((9, 8), Image.Resampling.LANCZOS).getdata())
        a = list(gray.resize((8, 8), Image.Resampling.LANCZOS).getdata())
        mean = sum(a) / len(a)
        pixel_hash = hashlib.sha256(str(rgb.size).encode() + rgb.tobytes()).hexdigest()
        return {'sha256': sha256(path), 'bytes': Path(path).stat().st_size,
                'format': fmt, 'mode': mode, 'width': size[0], 'height': size[1],
                'display_width': rgb.width, 'display_height': rgb.height,
                'decoded_pixel_sha256': pixel_hash,
                'dhash': bits_hex(d[y*9+x] > d[y*9+x+1] for y in range(8) for x in range(8)),
                'ahash': bits_hex(v > mean for v in a), 'exif_tag_count': len(exif),
                'selected_exif_metadata': sensitive}


def grouped(rows, key):
    groups = defaultdict(list)
    for r in rows:
        groups[r[key]].append(r['file'])
    return [sorted(v) for v in groups.values() if len(v) > 1]


def candidate_components(rows, pairs):
    parent = {r['file']: r['file'] for r in rows}
    def root(k):
        while parent[k] != k:
            k = parent[k]
        return k
    for p in pairs:
        parent[root(p['b'])] = root(p['a'])
    groups = defaultdict(list)
    for name in sorted(parent):
        groups[root(name)].append(name)
    return list(groups.values())


def font(size):
    try:
        return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', size)
    except OSError:
        return ImageFont.load_default(size=size)


def visuals(rows, extracted, out):
    """All thumbnails/crops are review aids, NOT segmentation/bounding-box annotations."""
    colors = {'good': '#1b7947', 'bad': '#ad2935', 'review': '#986400'}
    (out/'crops').mkdir(exist_ok=True)
    pages = []
    for start in range(0, len(rows), 9):
        batch = rows[start:start+9]
        sheet = Image.new('RGB', (1800, 3*560+70), '#ededed')
        draw = ImageDraw.Draw(sheet)
        draw.text((20, 12), 'PRELIMINARY VISUAL LABELS - not measured depth / verified TWI', fill='black', font=font(25))
        for j, r in enumerate(batch):
            x, y = (j%3)*600, 70+(j//3)*560
            with Image.open(extracted/r['file']) as image:
                image = ImageOps.exif_transpose(image).convert('RGB')
                thumb = ImageOps.contain(image, (580, 450))
                sheet.paste(thumb, (x+(600-thumb.width)//2, y))
                # Explicit center crop only: never presented as a labelled tread ROI.
                side = min(image.size)
                box = ((image.width-side)//2, (image.height-side)//2,
                       (image.width+side)//2, (image.height+side)//2)
                crop = image.crop(box)
                crop.thumbnail((1000, 1000))
                canvas = Image.new('RGB', (max(crop.width, 700), crop.height+90), 'white')
                canvas.paste(crop, ((canvas.width-crop.width)//2, 0))
                cd = ImageDraw.Draw(canvas)
                cd.text((8, crop.height+5), f"{r['index']:02} {r['label']} | YAML confidence {r['confidence']}", fill=colors[r['label']], font=font(20))
                cd.text((8, crop.height+34), 'CENTER CROP - not an annotated tread/TWI ROI', fill='black', font=font(17))
                canvas.save(out/'crops'/f"{r['index']:02}_{Path(r['file']).stem}_{r['label']}.jpg", quality=92)
            draw.text((x+10, y+455), f"{r['index']:02} {r['label']} | conf={r['confidence']} (uncalibrated)", fill=colors[r['label']], font=font(21))
            draw.text((x+10, y+487), Path(r['file']).stem[:23], fill='black', font=font(19))
            draw.text((x+10, y+517), f"{r['width']} x {r['height']} | review_required={r['review_required']}", fill='black', font=font(17))
        dest = out/f'contact_sheet_{start//9+1:02}.jpg'
        sheet.save(dest, quality=92)
        pages.append(dest.name)
    return pages


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, default=ROOT/'data/raw/TWI_1_1.zip')
    p.add_argument('--output', type=Path, default=ROOT/'artifacts')
    p.add_argument('--extract-dir', type=Path, default=ROOT/'data/extracted')
    p.add_argument('--export-review', type=Path, help='Optional local output directory, e.g. /mnt/c/.../twi-review')
    args = p.parse_args(argv)
    archive_hash = sha256(args.archive)
    if archive_hash != EXPECTED_SHA256:
        raise ValueError('Unexpected archive SHA256; deliberate code review required for new dataset version')
    entries = safe_extract(args.archive, args.extract_dir)
    label_path = args.extract_dir/'TWI/TWI_labels.yaml'
    data = yaml.safe_load(label_path.read_text(encoding='utf-8'))
    image_names = {e['file'] for e in entries if not e['directory'] and Path(e['file']).suffix.lower() in ('.jpg', '.jpeg', '.png')}
    errors = validate_labels(data, image_names)
    if errors:
        args.output.mkdir(parents=True, exist_ok=True)
        write_json(args.output/'validation_errors.json', errors)
        raise ValueError('Label schema failed; see validation_errors.json')
    rows = []
    for index, label in enumerate(data['images'], 1):
        r = {'index': index, **label}
        try:
            r.update(fingerprint(args.extract_dir/label['file']))
            r['decode_ok'] = True
        except Exception as e:
            r.update(decode_ok=False, error=str(e))
            errors.append(f"Decode failed: {r['file']}: {e}")
        rows.append(r)
    valid = [r for r in rows if r['decode_ok']]
    pairs = []
    for a, b in itertools.combinations(valid, 2):
        dd, ad = hamming(a['dhash'], b['dhash']), hamming(a['ahash'], b['ahash'])
        pairs.append({'a': a['file'], 'b': b['file'], 'dhash_distance': dd,
                      'ahash_distance': ad, 'exact_bytes': a['sha256'] == b['sha256'],
                      'candidate': a['decoded_pixel_sha256'] == b['decoded_pixel_sha256'] or (dd <= 6 and ad <= 6)})
    pairs.sort(key=lambda p: (p['dhash_distance']+p['ahash_distance'], p['a'], p['b']))
    by_name = {r['file']: r for r in valid}
    duplicate_claims = []
    for r in valid:
        if r.get('duplicate_of'):
            match = r['duplicate_of'] in by_name and r['sha256'] == by_name[r['duplicate_of']]['sha256']
            duplicate_claims.append({'file': r['file'], 'duplicate_of': r['duplicate_of'], 'verified_exact_bytes': match})
            if not match:
                errors.append(f"Unverified declared duplicate: {r['file']}")
    exact_groups = grouped(valid, 'sha256')
    for group in exact_groups:
        if len({by_name[n]['label'] for n in group}) != 1:
            errors.append(f'Conflicting labels among exact duplicates: {group}')
    unique = {r['sha256']: r for r in valid}
    binary = [r for r in unique.values() if r['label'] in ('good', 'bad') and not r['review_required']]
    candidates = [p for p in pairs if p['candidate']]
    summary = {
        'warning': 'Preliminary photo-based visual labels: NOT measured tread depth or direct TWI verification. No model evaluation performed.',
        'archive_sha256': archive_hash, 'archive_bytes': args.archive.stat().st_size,
        'archive_entries': len(entries), 'archive_files': sum(not e['directory'] for e in entries),
        'uncompressed_bytes': sum(e['bytes'] for e in entries),
        'image_count': len(image_names), 'label_count': len(rows), 'decode_ok': len(valid),
        'label_counts': dict(sorted(Counter(r['label'] for r in rows).items())),
        'review_required_count': sum(r['review_required'] for r in rows),
        'unique_byte_images': len(unique),
        'unique_byte_label_counts': dict(sorted(Counter(r['label'] for r in unique.values()).items())),
        'binary_eligible_after_exact_dedupe': len(binary),
        'binary_eligible_counts': dict(sorted(Counter(r['label'] for r in binary).items())),
        'exact_duplicate_groups': exact_groups,
        'decoded_pixel_duplicate_groups': grouped(valid, 'decoded_pixel_sha256'),
        'declared_duplicate_verification': duplicate_claims,
        'near_duplicate_method': 'EXIF-normalized RGB; 64-bit dHash + aHash; candidate if both Hamming <=6 or identical decoded pixels. Heuristic only: crop/rotation/same-tyre repeats can be missed; visually confirm all candidates and nearest pairs.',
        'near_candidate_pairs': candidates,
        'candidate_components_not_verified_tyre_ids': candidate_components(valid, candidates),
        'width_range': [min(r['width'] for r in valid), max(r['width'] for r in valid)] if valid else [],
        'height_range': [min(r['height'] for r in valid), max(r['height'] for r in valid)] if valid else [],
        'dimensions_histogram': dict(sorted(Counter(f"{r['width']}x{r['height']}" for r in valid).items())),
        'images_with_exif': sum(r['exif_tag_count'] > 0 for r in valid),
        'annotation_confidence_range': [min(r['confidence'] for r in rows), max(r['confidence'] for r in rows)],
        'confidence_provenance': 'Unspecified in YAML; NOT calibrated prediction probabilities or truth assurance.',
        'yaml_metadata_keys': sorted(k for k in data if k != 'images'),
        'per_image_keys': sorted(set().union(*(set(r) for r in data['images']))),
        'missing_for_visual_evaluation': ['independent tyre/vehicle/session/source IDs', 'expert adjudication and annotator provenance', 'licence/consent/provenance', 'locked train/validation/test assignment', 'representative prospective independent-tyre test set'],
        'physical_measurements_absent_and_out_of_current_scope': ['physical depth mm with measurement locations', 'direct TWI verification'],
        'validation_errors': errors,
        'runtime': {'python': platform.python_version(), 'pillow': pillow_version, 'pyyaml': yaml.__version__},
        'training_performed': False, 'inference_performed': False, 'split_created': False,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    sheets = visuals(valid, args.extract_dir, args.output)
    summary['contact_sheets'] = sheets
    write_json(args.output/'summary.json', summary)
    write_json(args.output/'manifest.json', rows)
    write_json(args.output/'archive_manifest.json', entries)
    write_json(args.output/'similarity_pairs.json', pairs)
    write_json(args.output/'yaml_metadata.json', {k:v for k,v in data.items() if k != 'images'})
    checklist = args.output/'label_review_checklist.csv'
    # Human review decisions are append/edit artefacts: never clobber on rerun.
    if not checklist.exists():
        with checklist.open('w', newline='', encoding='utf-8') as f:
            fields = ['index','file','original_label','original_confidence','original_reason','status',
                      'visual_review_performed','suggested_label','reviewer','rationale','tyre_group_id']
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in rows:
                w.writerow({'index': r['index'], 'file': r['file'], 'original_label': r['label'],
                            'original_confidence': r['confidence'], 'original_reason': r['reason'],
                            'status': 'unassessable' if r['label'] == 'review' else 'provisional',
                            'visual_review_performed': False, 'rationale': 'Pending independent visual/expert review; routing based on YAML only.'})
    if args.export_review:
        import shutil
        args.export_review.mkdir(parents=True, exist_ok=True)
        for name in [*sheets, 'summary.json', 'manifest.json', 'similarity_pairs.json']:
            shutil.copyfile(args.output/name, args.export_review/name)
        export_checklist = args.export_review/'label_review_checklist.csv'
        if not export_checklist.exists():
            shutil.copyfile(checklist, export_checklist)
        shutil.copytree(args.output/'crops', args.export_review/'crops', dirs_exist_ok=True)
    print(json.dumps({k: summary[k] for k in ['archive_sha256','image_count','decode_ok','label_counts',
                     'unique_byte_images','binary_eligible_after_exact_dedupe','binary_eligible_counts',
                     'width_range','height_range','near_candidate_pairs','validation_errors']}, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
