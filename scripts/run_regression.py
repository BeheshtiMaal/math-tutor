"""Offline unittest discovery with a reproducible JSON result and local log."""
import argparse,faulthandler,json,logging,sys,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='sources/manifests/phase_w9_regression.json');args=parser.parse_args()
    logging.getLogger('asyncio').setLevel(logging.ERROR)
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    log_path=ROOT/'.cache/regression.log';log_path.parent.mkdir(parents=True,exist_ok=True)
    started=time.monotonic()
    with log_path.open('w',encoding='utf-8',buffering=1) as log:
        faulthandler.enable(file=log);faulthandler.dump_traceback_later(120,repeat=True,file=log)
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
        faulthandler.cancel_dump_traceback_later()
    record={'tests':result.testsRun,'passed':result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),
            'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
            'elapsed_seconds':round(time.monotonic()-started,3),
            'failed_cases':[case.id() for case,_ in result.failures+result.errors],
            'skip_reasons':[{'case':case.id(),'reason':reason} for case,reason in result.skipped]}
    target=ROOT/args.output;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record));return not result.wasSuccessful()
if __name__=='__main__':raise SystemExit(main())
