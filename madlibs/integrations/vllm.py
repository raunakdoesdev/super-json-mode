from typing import Dict, List, Optional
import vllm
from vllm import SamplingParams
from madlibs.data.parser import SchemaBatcher, SchemaItem, insert_into_path
from madlibs.data.prompts import DEFAULT_PROMPT, SINGLE_PASS_PROMPT
from pydantic import BaseModel


class StructuredVLLMModel:
    def __init__(self, model_id):
        self.llm = vllm.LLM(model=model_id)

    def generate_prompt(
        self,
        prompt: str,
        batch_item: SchemaItem,
        extraction_prompt_template: str = DEFAULT_PROMPT,
    ):
        """Generate a prompt for a single item in a batch."""

        return extraction_prompt_template.format(
            prompt=prompt, key=batch_item.path[-1], type=batch_item.type_
        )

    def generate(
        self,
        prompt: str,
        extraction_prompt_template: str = DEFAULT_PROMPT,
        schema: str or BaseModel = None,
        batch_size: int = 4,
        # max_new_tokens needs to be large enough to fit the largest value in the schema
        max_new_tokens: int = 20,
        use_constrained_sampling=True,
        dag: Optional[Dict[str, List[str]]] = None,
        **kwargs,
    ):
        schema_batcher = SchemaBatcher(schema, dag=dag, batch_size=batch_size)
        batches = schema_batcher.batches

        output_json = {}

        for batch in batches:
            prompts = [
                self.generate_prompt(
                    prompt, item, extraction_prompt_template=extraction_prompt_template
                )
                for item in batch.items
            ]

            sampling_params = SamplingParams(**kwargs)
            sampling_params.max_tokens = max_new_tokens
            if use_constrained_sampling:
                # TODO: implement constrained sampling on the logits
                sampling_params.logits_processors = []

            results = self.llm.generate(prompts, sampling_params=sampling_params)
            outputs = [result.outputs[0].text for result in results]

            for item, output in zip(batch.items, outputs):
                insert_into_path(output_json, item.path, output.strip())

        return output_json

    def default_generate(
        self,
        prompt: str,
        extraction_prompt_template: str = SINGLE_PASS_PROMPT,
        schema: str or BaseModel = None,
        # max_new_tokens needs to be large enough to fit the filled-in schema
        max_new_tokens: int = 256,
        **kwargs,
    ):
        prompt = extraction_prompt_template.format(prompt=prompt, schema=schema)

        sampling_params = SamplingParams(**kwargs)
        sampling_params.max_tokens = max_new_tokens

        result = self.llm.generate(prompt, sampling_params=sampling_params)[0]
        output = result.outputs[0].text
        return output
