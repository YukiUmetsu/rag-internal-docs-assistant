const PROMPTS = [
  "What was the refund window in 2025?",
  "How many PTO days do employees get?",
  "Known Issues",
  "SEV2",
  "When is manager approval required for refunds?"
];

type Props = {
  onSelect: (prompt: string) => void;
};

export function ExamplePrompts({ onSelect }: Props) {
  return (
    <section className="examples" aria-label="Example prompts">
      <p>Good demo prompts</p>
      <div>
        {PROMPTS.map((prompt) => (
          <button key={prompt} type="button" onClick={() => onSelect(prompt)}>
            {prompt}
          </button>
        ))}
      </div>
    </section>
  );
}
