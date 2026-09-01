import ChatSection from '~/components/sections/search/chat';

export function meta() {
  return [
    { title: 'Assistant | Multiscale Model Portal | MISM' },
    {
      name: 'description',
      content:
        'Multiscale Immune Systems Modeling - Multiscale Model Portal - Ask about multiscale models and tools in natural language',
    },
  ];
}

export default function Chat() {
  return <ChatSection />;
}
