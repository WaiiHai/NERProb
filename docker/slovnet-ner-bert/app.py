
from os import getenv

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)-15s %(message)s'
)
log = logging.info

from aiohttp import web

import torch
torch.set_grad_enabled(False)

from slovnet.const import PER, LOC, ORG, CUDA0
from slovnet.vocab import (
    BERTVocab,
    BIOTagsVocab
)
from slovnet.model.bert import (
    RuBERTConfig,
    BERTEmbedding,
    BERTEncoder,
    BERTNERHead,
    BERTNER
)
from slovnet.encoders.bert import BERTInferEncoder
from slovnet.infer.bert import BERTNERInfer, BERTTagsDecoder


WORDS_VOCAB = getenv('WORDS_VOCAB', 'vocab.txt')
EMB = getenv('EMB', 'emb.pt')
ENCODER = getenv('ENCODER', 'encoder.pt')
NER = getenv('NER', 'ner.pt')

DEVICE = getenv('DEVICE', CUDA0)
SEQ_LEN = int(getenv('SEQ_LEN', 128))
BATCH_SIZE = int(getenv('BATCH_SIZE', 32))

HOST = getenv('HOST', '0.0.0.0')
PORT = int(getenv('PORT', 8080))


log('Load words vocab: %r' % WORDS_VOCAB)
words_vocab = BERTVocab.load(WORDS_VOCAB)
tags_vocab = BIOTagsVocab([PER, LOC, ORG])

config = RuBERTConfig()
emb = BERTEmbedding.from_config(config)
encoder = BERTEncoder.from_config(config)
ner = BERTNERHead(config.emb_dim, len(tags_vocab))
model = BERTNER(emb, encoder, ner)
model.eval()

log('Load emb: %r' % EMB)
model.emb.load(EMB)
log('Load encoder: %r' % ENCODER)
model.encoder.load(ENCODER)
log('Load ner: %r' % NER)
model.ner.load(NER)
log('Device: %r' % DEVICE)
model = model.to(DEVICE)

log('Seq len: %r' % SEQ_LEN)
log('Batch size: %r' % BATCH_SIZE)
encoder = BERTInferEncoder(
    words_vocab,
    seq_len=SEQ_LEN, batch_size=BATCH_SIZE
)
decoder = BERTTagsDecoder(tags_vocab)
infer = BERTNERInfer(model, encoder, decoder)


async def handle(request):
    chunk = await request.json()
    log('Post chunk size: %r' % len(chunk))
    markups = list(infer(chunk))

    spans = sum(len(_.spans) for _ in markups)
    log('Infer spans: %r', spans)

    data = [_.as_json for _ in markups]
    return web.json_response(data)


app = web.Application()
app.add_routes([web.post('/', handle)])

web.run_app(app, host=HOST, port=PORT)
