import tensorflow as tf
from transformers import GPT2Config, TFGPT2LMHeadModel
from transformers import TFGPT2LMHeadModel
from transformers import BertTokenizer, GPT2Tokenizer
import configs
from transformers import TextGenerationPipeline
import time
import pickle
from pathlib import Path
import numpy as np


max_length = configs.model.max_length


def load_tokenizer() -> BertTokenizer:
    tokenizer = BertTokenizer.from_pretrained(
        configs.data.path, max_len=max_length)
    tokenizer.return_attention_mask = None
    return tokenizer


def get_dataset() -> tf.data.Dataset:
    p = Path(configs.data.path)
    pickle_files = p.glob('*.pickle')
    ids, labels = [], []
    for pickle_file in pickle_files:
        print(f"loading {pickle_file}")
        _ids, _labels = pickle.load(open(pickle_file, 'rb'))
        if len(ids) == 0:
            ids = _ids
            labels = _labels
        else:
            ids = np.vstack((ids, _ids))
            labels = np.vstack((labels, _labels))
    print(ids.shape, labels.shape, ids.dtype, labels.dtype)
    dataset = tf.data.Dataset.from_tensor_slices((
        ids,
        labels
    )).shuffle(ids.shape[0], reshuffle_each_iteration=True).batch(configs.model.batch_size)
    return dataset


def init_model(tokenizer, model_path=configs.model_path) -> TFGPT2LMHeadModel:

    try:
        model = TFGPT2LMHeadModel.from_pretrained(model_path, return_dict=True)
    except EnvironmentError:
        config = GPT2Config(
            architectures=["TFGPT2LMHeadModel"],
            model_type="TFGPT2LMHeadModel",
            tokenizer_class="BertTokenizer",
            vocab_size=tokenizer.vocab_size,
            n_positions=configs.model.n_positions,
            n_ctx=configs.model.n_ctx,
            n_embd=configs.model.n_embd,
            n_layer=configs.model.n_layer,
            n_head=configs.model.n_head,
            pad_token_id=tokenizer.pad_token_id,
            task_specific_params={
                "text-generation": {
                    "do_sample": True,
                    "max_length": 120
                }
            },
        )
        model = TFGPT2LMHeadModel(config)

    loss = model.compute_loss
    optimizer = tf.keras.optimizers.Adam(learning_rate=1e-5, epsilon=1e-08)
    metrics = [
        tf.keras.metrics.SparseCategoricalAccuracy('accuracy')
    ]

    model.compile(
        optimizer=optimizer,
        loss=[loss, *[None] * model.config.n_layer],
    )

    return model


def train():
    tokenizer = load_tokenizer()
    train_dataset = get_dataset()
    model = init_model(tokenizer, configs.model_path)

    class AutoSaveCallback(tf.keras.callbacks.Callback):
        def on_epoch_end(self, epoch, logs=None):
            self.model.save_pretrained(f'{configs.model_path}')

    callbacks = [
        tf.keras.callbacks.TensorBoard(log_dir=f'{configs.model_path}/logs'),
        tf.keras.callbacks.ModelCheckpoint(filepath=configs.model_path,
                                           save_weights_only=True),
        AutoSaveCallback()
    ]

    t1 = time.time()
    model.fit(
        train_dataset,
        epochs=50,
        steps_per_epoch=2000,
        callbacks=callbacks,
        batch_size=None
    )
    print(f'total train time {time.time() - t1}')


if __name__ == '__main__':
    train()
