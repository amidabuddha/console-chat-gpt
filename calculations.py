import tiktoken
import toml
import locale

import styling


def calculate_costs(prompt, completion, in_cost, out_cost):
    """
    Calculates the price for the given conversation.
    """
    prompt_cost = prompt * in_cost / 1000
    completions_cost = completion * out_cost / 1000
    chat_cost = prompt_cost + completions_cost
    return prompt_cost, completions_cost, chat_cost


def print_costs(
    conversation_tokens: float,
    conversation_prompt_tokens: float,
    conversation_total_prompts_tokens: float,
    conversation_completion_tokens: float,
    conversation_total_completions_tokens: float,
    calculated_prompt_tokens: float,
    calculated_completion_max_tokens: float,
    input_cost: float,
    output_cost: float,
    api_cost: float,
    debug: bool,
):
    """
    Prints the total used tokens and price.
    """
    (
        _,
        _,
        conversation_cost,
    ) = calculate_costs(
        conversation_total_prompts_tokens,
        conversation_total_completions_tokens,
        input_cost,
        output_cost,
    )
    if debug:
        styling.coloring(
            None,
            "green",
            tokens_used=conversation_tokens,
            calculated_prompt_tokens=calculated_prompt_tokens,
            prompt_tokens_used=conversation_prompt_tokens,
            total_prompt_tokens_used=conversation_total_prompts_tokens,
            calculated_completion_max_tokens=calculated_completion_max_tokens,
            completion_tokens_used=conversation_completion_tokens,
            total_completion_tokens_used=conversation_total_completions_tokens,
            chat_cost=locale.currency(conversation_cost, grouping=True),
            api_key_usage_cost=locale.currency(api_cost, grouping=True),
        )
    else:
        styling.coloring(
            None,
            "green",
            tokens_used=conversation_tokens,
            chat_cost=locale.currency(conversation_cost, grouping=True),
            api_usage_cost=locale.currency(api_cost, grouping=True),
        )


def update_api_usage(
    path,
    conversation_prompt_tokens,
    conversation_completion_tokens,
    input_cost,
    output_cost,
    usage,
):
    """
    Calculates the total conversation expences made in the current environment.
    """
    _, _, api_usage_cost = calculate_costs(
        conversation_prompt_tokens,
        conversation_completion_tokens,
        input_cost,
        output_cost,
    )
    api_usage_cost += usage
    data = toml.load(path)
    data["chat"]["api"]["api_usage"] = float(api_usage_cost)
    with open(path, "w") as toml_file:
        toml.dump(data, toml_file)


def num_tokens_from_messages(messages, model):
    """
    Count the tokens of the next user propmpt
    """
    encoding = tiktoken.encoding_for_model(model)
    tokens_per_message = 3
    tokens_per_name = 1
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3
    return num_tokens
